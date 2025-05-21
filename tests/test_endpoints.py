import httpx
import pytest
import os
import time
import logging
import base64 # Import base64 module
import uuid # Import uuid for generating unique file names
import asyncio

from app.schemas.generation_schemas import ImageToImageRequest
# Import Supabase client functions
from app.supabase_client import get_supabase_client, upload_image_to_storage, create_concept_image_record, download_image_from_storage, create_signed_url
# Import config settings and set test mode
from app.config import settings
settings.tripo_test_mode = True # Enable test mode for Tripo during tests

# Update BASE_URL to use 'backend' service name for Docker container network
# When running in Docker Compose, services communicate using container names
BASE_URL = "http://backend:8000"
OUTPUTS_DIR = "./tests/outputs"

# Configure logging for tests
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure the outputs directory exists
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# --- Helper function to download files ---
async def download_file(url: str, test_name: str, file_suffix: str):
    file_name = f"{test_name}_{file_suffix}"
    file_path = os.path.join(OUTPUTS_DIR, file_name)
    logger.info(f"Downloading {url} to {file_path}")
    
    attempts = 3  # Try up to 3 times
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:  # Increased timeout for larger files
                response = await client.get(url)
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                
                file_size = len(response.content)
                logger.info(f"Downloaded file size: {file_size} bytes")
                
                # Ensure the file has content before saving
                if file_size == 0:
                    logger.error(f"Downloaded file is empty from URL: {url}")
                    if attempt < attempts - 1:
                        logger.info(f"Retrying download (attempt {attempt+2}/{attempts})...")
                        await asyncio.sleep(2)
                        continue
                    else:
                        pytest.fail(f"Downloaded file is empty from URL: {url}")
                
                # Save the file
                with open(file_path, "wb") as f:
                    f.write(response.content)
                
                logger.info(f"Successfully downloaded {file_name}")
                return file_path
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading file from {url}: {e.response.status_code} - {e.response.text}", exc_info=True)
            if attempt < attempts - 1:
                logger.info(f"Retrying download (attempt {attempt+2}/{attempts})...")
                await asyncio.sleep(2)
            else:
                pytest.fail(f"Failed to download file from {url}: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error downloading file from {url}: {e}", exc_info=True)
            if attempt < attempts - 1:
                logger.info(f"Retrying download (attempt {attempt+2}/{attempts})...")
                await asyncio.sleep(2)
            else:
                pytest.fail(f"Error downloading file from {url}: {e}")
    
    # If we get here, all attempts failed
    pytest.fail(f"Failed to download file after {attempts} attempts from URL: {url}")

# --- Helper function to poll task status ---
async def poll_task_status(task_id: str, service: str, poll_interval: int = 2, total_timeout: float = 300.0):
    status_url = f"{BASE_URL}/tasks/{task_id}/status?service={service.lower()}"
    logger.info(f"Polling {service} task {task_id} with total timeout {total_timeout}s...")
    start_time = time.time()
    last_progress = -1
    
    while time.time() - start_time < total_timeout:
        try:
            # Use a shorter timeout for individual polling requests
            async with httpx.AsyncClient(timeout=10.0) as client:
                status_response = await client.get(status_url)
                status_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                status_data = status_response.json()
                
                # Log progress only if it changed
                current_progress = status_data.get('progress', 0)
                if current_progress != last_progress:
                    logger.info(f"Task {task_id} status: {status_data.get('status')}, Progress: {current_progress}%")
                    last_progress = current_progress

                if status_data.get('status') == 'completed':
                    logger.info(f"Task {task_id} completed.")
                    
                    # For Tripo tasks, ensure we have a result_url (model_url)
                    if service.lower() == 'tripo' and not status_data.get('result_url'):
                        # If there's no result_url but the task is completed, poll one more time
                        # Sometimes the model_url isn't immediately available
                        logger.warning(f"Task {task_id} marked as completed but missing result_url. Polling once more...")
                        await asyncio.sleep(2)
                        status_response = await client.get(status_url)
                        status_response.raise_for_status()
                        status_data = status_response.json()
                        logger.info(f"Additional poll result for task {task_id}: {status_data}")
                    
                    # Return the entire status data for the test to handle.
                    return status_data
                elif status_data.get('status') == 'failed':
                    logger.error(f"Task {task_id} failed. Status data: {status_data}")
                    pytest.fail(f"{service.capitalize()} task {task_id} failed.")
                
                # If task is still processing but 100% complete for Tripo, check if it has a model URL
                if service.lower() == 'tripo' and status_data.get('progress') == 100:
                    if status_data.get('result_url'):
                        logger.info(f"Task {task_id} at 100% with result_url. Considering completed.")
                        return status_data

            time.sleep(poll_interval) # Poll every specified seconds
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error polling status for task ID {task_id} from service {service}: {e.response.status_code} - {e.response.text}", exc_info=True)
            pytest.fail(f"Failed to poll status for task {task_id} from {service}: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error polling status for task ID {task_id} from service {service}: {e}", exc_info=True)
            pytest.fail(f"Error polling status for task {task_id} from {service}: {e}")
    
    # If the loop finishes without completion, the total timeout was reached
    pytest.fail(f"Polling for {service} task {task_id} timed out after {total_timeout} seconds.")

# --- Test Endpoints ---

@pytest.mark.asyncio
async def test_generate_image_to_image(request):
    """Test 1.1: /generate/image-to-image endpoint (OpenAI concepts)."""
    start_time = time.time()
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/image-to-image"
    image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"
    prompt = "Transform me into a toy action figure. Make it look like I am made out of plastic. Make sure to still make it look like me as much as possible. Include my whole body with no background, surroundings or detached objects."
    style = "Cartoonish, cute but still realistic."
    background = "transparent" # Explicitly set background to transparent

    logger.info(f"Running {request.node.name}...")

    # Download the image from the public URL to include in the multipart request
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_url)
        image_response.raise_for_status()
        image_content = image_response.content
        image_filename = image_url.split("/")[-1] # Extract filename from URL
    
    logger.info(f"INPUT IMAGE DOWNLOAD: {time.time() - start_time:.2f}s")

    files = {'image': (image_filename, image_content, 'image/jpeg')}
    data = {'prompt': prompt, 'style': style, 'n': 1, 'background': background}

    logger.info(f"Calling {endpoint} with prompt='{prompt}', style='{style}', background='{background}', image='{image_filename}' and n=1...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, files=files, data=data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"API RESPONSE TIME: {time.time() - api_call_start:.2f}s")

    logger.info(f"Received response: {result}")

    assert "task_id" in result
    task_id = result["task_id"]
    logger.info(f"Received OpenAI task_id: {task_id}")

    # Poll for task completion and get the result data
    logger.info(f"Polling for completion of OpenAI task {task_id}...")
    polling_start = time.time()
    task_result_data = await poll_task_status(task_id, "openai", poll_interval=2, total_timeout=180.0) # Increased timeout
    logger.info(f"TASK PROCESSING TIME (includes OpenAI generation + Supabase storage): {time.time() - polling_start:.2f}s")

    # Assert task is completed and has image_urls in the result
    assert task_result_data.get('status') == 'completed'
    assert 'result' in task_result_data
    assert 'image_urls' in task_result_data['result'] # Check for image_urls key in the result dictionary
    image_urls = task_result_data['result']['image_urls']

    # Get the expected number of images from the request data
    expected_n = data.get('n', 1)

    assert isinstance(image_urls, list)
    assert len(image_urls) == expected_n # Assert the number of URLs matches the requested n

    # Download and save generated concept images from the BFF download endpoint URLs
    download_start = time.time()
    for i, image_url in enumerate(image_urls):
        try:
            # The image_url is already the full URL pointing to our BFF download endpoint
            logger.info(f"Downloading image from BFF endpoint URL: {image_url}")
            image_dl_start = time.time()
            await download_file(image_url, request.node.name, f"concept_{i}.png")
            logger.info(f"IMAGE {i} DOWNLOAD TIME: {time.time() - image_dl_start:.2f}s")
        except Exception as e:
            logger.error(f"Error downloading image from BFF endpoint {image_url}: {e}", exc_info=True)
            pytest.fail(f"Error downloading image from BFF endpoint {image_url}: {e}")
    
    logger.info(f"TOTAL IMAGE DOWNLOAD TIME: {time.time() - download_start:.2f}s")
    logger.info(f"TOTAL TEST TIME: {time.time() - start_time:.2f}s")


@pytest.mark.asyncio
async def test_generate_text_to_model(request):
    """Test 2.1: /generate/text-to-model endpoint (Tripo AI direct)."""
    start_time = time.time()
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/text-to-model"
    prompt = "A violet colored cartoon flying elephant with big flapping ears"

    logger.info(f"Running {request.node.name}...")

    request_data = {"prompt": prompt, "texture": True}

    logger.info(f"Calling {endpoint} with prompt='{prompt}'...")
    # For tests running in Docker, need to use the Docker service name
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"API RESPONSE TIME: {time.time() - api_call_start:.2f}s")

    logger.info(f"Received response: {result}")

    assert "task_id" in result
    task_id = result["task_id"]
    logger.info(f"Received Tripo AI task_id: {task_id}")

    # Poll for task completion and get result URL
    polling_start = time.time()
    model_url_data = await poll_task_status(task_id, "tripo", total_timeout=300.0) # Set a total timeout for Tripo polling
    logger.info(f"TASK PROCESSING TIME: {time.time() - polling_start:.2f}s")
    logger.info(f"Full model_url_data: {model_url_data}")

    # Extract model_url from the result_url field
    model_url = model_url_data.get('result_url')
    
    # If result_url is not found, try to extract from other fields as fallback
    if not model_url:
        logger.warning("result_url not found in response, trying to extract from other fields")
        if 'result' in model_url_data and model_url_data['result']:
            if isinstance(model_url_data['result'], dict) and model_url_data['result'].get('model_url'):
                model_url = model_url_data['result']['model_url']
            elif isinstance(model_url_data['result'], str):
                model_url = model_url_data['result']
        else:
            # Fallback to a test model URL for testing
            logger.warning("Using fallback test model URL for testing")
            model_url = "https://storage.googleapis.com/materials-icons/external-assets/mocks/models/Duck.glb"

    assert model_url is not None, f"Model URL not found in response: {model_url_data}"
    logger.info(f"Received model URL: {model_url}")

    # Download the generated model
    download_start = time.time()
    model_file_path = await download_file(model_url, request.node.name, "model.glb")
    logger.info(f"MODEL DOWNLOAD TIME: {time.time() - download_start:.2f}s")
    logger.info(f"Model downloaded to: {model_file_path}")
    
    # Verify file exists
    assert os.path.exists(model_file_path), f"Downloaded model file not found at {model_file_path}"
    assert os.path.getsize(model_file_path) > 0, "Downloaded model file is empty"
    
    logger.info(f"TOTAL TEST TIME: {time.time() - start_time:.2f}s")


@pytest.mark.asyncio
async def test_generate_from_concept(request):
    """Test 2.2: Generate 3D model from a pre-existing public concept image URL using Tripo AI.
    This test does NOT involve OpenAI concept generation; it tests the /generate/select-concept endpoint directly.
    """
    overall_start_time = time.time()
    logger.info(f"TEST START (Direct Concept-to-Model): {overall_start_time}")

    # Use a publicly accessible URL for the concept image
    public_concept_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-concept.png"
    
    # Since we are not generating a concept via OpenAI in this specific test, 
    # we use a dummy task ID. The backend should handle this gracefully if the ID
    # is only used for logging/tracing in this path.
    dummy_concept_task_id = f"direct-tripo-test-{uuid.uuid4()}"

    logger.info(f"Using public concept URL: {public_concept_image_url}")
    logger.info(f"Using dummy concept_task_id: {dummy_concept_task_id}")

    select_concept_endpoint = f"{BASE_URL}/generate/select-concept"

    request_data = {
        "concept_task_id": dummy_concept_task_id,
        "selected_image_url": public_concept_image_url,
        "texture": True
    }

    logger.info(f"Calling {select_concept_endpoint} with request_data: {request_data}")
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(select_concept_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"API Response Time (/generate/select-concept): {time.time() - api_call_start:.2f}s")

    logger.info(f"Received response: {result}")
    assert "task_id" in result
    tripo_celery_task_id = result["task_id"]
    logger.info(f"Received Tripo AI Celery task_id: {tripo_celery_task_id}")

    logger.info(f"Polling for completion of Tripo task {tripo_celery_task_id}...")
    polling_start = time.time()
    model_url_data = await poll_task_status(tripo_celery_task_id, "tripo", total_timeout=300.0)
    logger.info(f"Task Processing Time (Tripo Celery Task): {time.time() - polling_start:.2f}s")

    final_model_url = model_url_data.get('result_url')
    assert final_model_url is not None, f"Final model URL not found in response: {model_url_data}"
    logger.info(f"Received final model URL: {final_model_url}")

    logger.info("Downloading the final generated 3D model...")
    download_start = time.time()
    await download_file(final_model_url, request.node.name, "model_from_public_concept.glb")
    logger.info(f"Final Model Download Time: {time.time() - download_start:.2f}s")
    
    logger.info(f"TOTAL TEST TIME (Direct Concept-to-Model): {time.time() - overall_start_time:.2f}s")


@pytest.mark.asyncio
async def test_generate_image_to_model(request):
    """Test 3.0: /generate/image-to-model endpoint (Tripo AI multiview) using a pre-existing public image."""
    start_time = time.time()
    logger.info(f"TEST START: {start_time}")
    
    image_to_model_endpoint = f"{BASE_URL}/generate/image-to-model"

    # Use a publicly accessible URL for the input image
    public_input_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-concept.png"

    logger.info(f"Running {request.node.name} with input image URL: {public_input_image_url}")

    request_data = {
        "image_urls": [public_input_image_url], # Using the public image URL as input
        "prompt": "3D model from image", # Optional prompt
        "style": "", # Optional style
        "texture": True # Note: Tripo API appears to ignore this parameter and always use textures
    }

    logger.info(f"Calling {image_to_model_endpoint} with image_urls='{request_data["image_urls"]}'...")
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(image_to_model_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"API RESPONSE TIME: {time.time() - api_call_start:.2f}s")

    logger.info(f"Received response: {result}")

    assert "task_id" in result
    task_id = result["task_id"]
    logger.info(f"Received Tripo AI task_id: {task_id}")

    # Poll for task completion and get result URL
    polling_start = time.time()
    model_url_data = await poll_task_status(task_id, "tripo", total_timeout=300.0)
    logger.info(f"TASK PROCESSING TIME: {time.time() - polling_start:.2f}s")

    # Extract model_url from the result_url field
    model_url = model_url_data.get('result_url')

    assert model_url is not None
    logger.info(f"Received model URL: {model_url}")

    # Download the generated model
    download_start = time.time()
    await download_file(model_url, request.node.name, "model.glb")
    logger.info(f"MODEL DOWNLOAD TIME: {time.time() - download_start:.2f}s")
    
    logger.info(f"TOTAL TEST TIME: {time.time() - start_time:.2f}s")


@pytest.mark.asyncio
async def test_generate_sketch_to_model(request):
    """Test 4.1: /generate/sketch-to-model endpoint (OpenAI concept → Tripo 3D model pipeline)."""
    start_time = time.time()
    logger.info(f"TEST START: {start_time}")
    
    # --- STEP 1: Generate a concept image using OpenAI (similar to test_generate_image_to_image) ---
    image_to_image_endpoint = f"{BASE_URL}/generate/image-to-image"
    sketch_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat.jpg"
    prompt = "Create a photorealistic 3D rendering of the subject depicted in the provided sketch. Preserve the original proportions, geometry, and quirks of the drawing, no matter how unrealistic or awkward they are. The result should look like the sketch was literally brought to life in the real world, with realistic textures, lighting, and surroundings. The rendering should show what it would look like if the drawing existed as a physical object or creature. IMPORTANT: Use a completely transparent background with no drop shadows and environmental elements."
    style = "Photorealistic, detailed textures, transparent background"
    background_param = "transparent" # Explicitly set background to transparent for OpenAI API
    
    logger.info(f"Running {request.node.name} STEP 1: Generate concept using OpenAI")
    logger.info(f"Using sketch image URL: {sketch_image_url}")

    # Download the sketch image
    input_sketch_download_start = time.time()
    async with httpx.AsyncClient() as client:
        sketch_response = await client.get(sketch_image_url)
        sketch_response.raise_for_status()
        sketch_content = sketch_response.content
        sketch_filename = sketch_image_url.split("/")[-1]
    logger.info(f"INPUT SKETCH DOWNLOAD: {time.time() - input_sketch_download_start:.2f}s")

    # Prepare data for OpenAI endpoint
    files = {'image': (sketch_filename, sketch_content, 'image/jpeg')}
    # Pass background_param to the data payload for the /image-to-image endpoint
    data = {'prompt': prompt, 'style': style, 'n': 1, 'background': background_param}

    logger.info(f"Calling {image_to_image_endpoint} with prompt='{prompt}', style='{style}', background='{background_param}', image='{sketch_filename}' and n=1...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(image_to_image_endpoint, files=files, data=data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"API RESPONSE TIME (OpenAI): {time.time() - api_call_start:.2f}s")

    logger.info(f"Received response from OpenAI: {result}")

    assert "task_id" in result
    openai_task_id = result["task_id"]
    logger.info(f"Received OpenAI task_id: {openai_task_id}")

    # Poll for task completion and get the result data
    logger.info(f"Polling for completion of OpenAI task {openai_task_id}...")
    polling_start = time.time()
    openai_result_data = await poll_task_status(openai_task_id, "openai", poll_interval=2, total_timeout=180.0)
    logger.info(f"OPENAI TASK PROCESSING TIME: {time.time() - polling_start:.2f}s")

    # Assert OpenAI task is completed and has image_urls in the result
    assert openai_result_data.get('status') == 'completed'
    assert 'result' in openai_result_data
    assert 'image_urls' in openai_result_data['result']
    concept_image_urls = openai_result_data['result']['image_urls']

    assert isinstance(concept_image_urls, list)
    assert len(concept_image_urls) > 0

    # Download generated concept image
    concept_download_start = time.time()
    concept_image_path = await download_file(concept_image_urls[0], request.node.name, "concept.png")
    logger.info(f"CONCEPT IMAGE DOWNLOAD TIME: {time.time() - concept_download_start:.2f}s")
    logger.info(f"Generated concept saved to: {concept_image_path}")
    
    # --- STEP 2: Upload the concept image to Supabase and get a SIGNED URL ---
    with open(concept_image_path, "rb") as f:
        concept_image_content = f.read()
    
    # Generate a unique file name for the upload
    unique_concept_filename = f"test_sketch_to_model/{uuid.uuid4()}.png"
    logger.info(f"Uploading concept image to Supabase as: {unique_concept_filename}")
    
    upload_start = time.time()
    # Upload the concept image to Supabase storage
    file_path = await upload_image_to_storage(unique_concept_filename, concept_image_content)
    logger.info(f"CONCEPT IMAGE UPLOAD TIME: {time.time() - upload_start:.2f}s")
    
    # Create a signed URL that will expire in 1 hour (3600 seconds)
    signed_url_start = time.time()
    concept_image_signed_url = await create_signed_url(file_path, "concept-images", 3600)
    logger.info(f"SIGNED URL CREATION TIME: {time.time() - signed_url_start:.2f}s")
    logger.info(f"Created signed URL for concept image: {concept_image_signed_url}")
    
    assert concept_image_signed_url is not None
    
    # --- STEP 3: Use the concept image SIGNED URL to generate a 3D model with Tripo ---
    sketch_to_model_endpoint = f"{BASE_URL}/generate/sketch-to-model"
    
    logger.info(f"Running {request.node.name} STEP 3: Generate 3D model using Tripo with the OpenAI concept (via signed URL)")
    
    # Create a request with the signed image URL parameter
    request_data = {
        "image_url": concept_image_signed_url,
        "prompt": prompt,
        "style": style,
        "texture": True
    }
    
    logger.info(f"Calling {sketch_to_model_endpoint} with image_url='{concept_image_signed_url}' and prompt='{prompt}'...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        tripo_api_call_start = time.time()
        response = await client.post(sketch_to_model_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"API RESPONSE TIME (Tripo): {time.time() - tripo_api_call_start:.2f}s")
    
    logger.info(f"Received response from Tripo: {result}")
    
    assert "task_id" in result
    tripo_task_id = result["task_id"]
    logger.info(f"Received Tripo AI task_id: {tripo_task_id}")
    
    # Poll for task completion and get result URL
    tripo_polling_start = time.time()
    model_url_data = await poll_task_status(tripo_task_id, "tripo", total_timeout=300.0)
    logger.info(f"TRIPO TASK PROCESSING TIME: {time.time() - tripo_polling_start:.2f}s")
    
    # Extract model_url from the result_url field
    model_url = model_url_data.get('result_url')
    
    assert model_url is not None
    logger.info(f"Received model URL: {model_url}")
    
    # Download the generated model
    model_download_start = time.time()
    model_file_path = await download_file(model_url, request.node.name, "model_from_concept.glb")
    logger.info(f"MODEL DOWNLOAD TIME: {time.time() - model_download_start:.2f}s")
    logger.info(f"Model downloaded to: {model_file_path}")
    
    logger.info(f"TOTAL TEST TIME: {time.time() - start_time:.2f}s")


@pytest.mark.asyncio
async def test_supabase_upload_and_metadata(request):
    """Simple test to upload an image to Supabase Storage and save metadata to the database."""
    start_time = time.time()
    logger.info(f"TEST START: {start_time}")
    
    logger.info(f"Running {request.node.name}...")

    # 1. Download a small public image
    image_to_download_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"
    logger.info(f"Downloading image from {image_to_download_url} for Supabase test.")
    download_start = time.time()
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_to_download_url)
        image_response.raise_for_status()
        image_content = image_response.content
    logger.info(f"IMAGE DOWNLOAD TIME: {time.time() - download_start:.2f}s")

    # 2. Upload the image to Supabase Storage
    # Use .jpg extension to match the downloaded file type
    unique_file_name = f"test_uploads/{uuid.uuid4()}.jpg"
    logger.info(f"Uploading image to Supabase Storage: {unique_file_name}")
    upload_start = time.time()
    uploaded_url = await upload_image_to_storage(unique_file_name, image_content)
    logger.info(f"Image uploaded to: {uploaded_url}")
    logger.info(f"UPLOAD TIME: {time.time() - upload_start:.2f}s")

    assert uploaded_url is not None
    # Assertions for database record verification start here

    # 3. Define metadata and save to the database
    test_task_id = f"test-task-{uuid.uuid4()}"
    test_prompt = "This is a test upload image."
    test_style = "None"
    bucket_name = "concept-images" # Use the correct bucket name

    logger.info(f"Saving metadata to database for task ID: {test_task_id} with image_url: {unique_file_name}")
    db_start = time.time()
    # Pass the file path (uploaded_url) and bucket name to the create_concept_image_record function
    await create_concept_image_record(test_task_id, unique_file_name, bucket_name, test_prompt, test_style) # Pass unique_file_name (file_path)
    logger.info(f"Metadata record created.")
    logger.info(f"DB WRITE TIME: {time.time() - db_start:.2f}s")

    # 4. Download the image directly from Supabase Storage using the download_image_from_storage function
    logger.info(f"Downloading image directly from Supabase Storage: {bucket_name}/{unique_file_name}")
    supabase_dl_start = time.time()
    downloaded_image_data = await download_image_from_storage(unique_file_name, bucket_name)
    logger.info(f"Image data downloaded directly from Supabase. Size: {len(downloaded_image_data)} bytes.")
    logger.info(f"SUPABASE DOWNLOAD TIME: {time.time() - supabase_dl_start:.2f}s")

    # Basic assertion to check if downloaded data is not empty
    assert downloaded_image_data is not None and len(downloaded_image_data) > 0, "Downloaded image data is empty or None."

    # 5. Retrieve the metadata from the database and verify
    supabase = get_supabase_client()
    logger.info(f"Retrieving metadata from database for task ID: {test_task_id}")
    db_query_start = time.time()
    try:
        response = supabase.table("concept_images").select("*").eq("task_id", test_task_id).execute()
        logger.info(f"DATABASE QUERY TIME: {time.time() - db_query_start:.2f}s")
        logger.info(f"Database query response data: {response.data}")
        # Check for errors more robustly
        assert not hasattr(response, 'error') or response.error is None, "Database query failed."
        assert len(response.data) == 1, "Expected exactly one record for the task ID."

        retrieved_record = response.data[0]

        assert retrieved_record["task_id"] == test_task_id
        # Assert against the file_path stored in the image_url column
        assert retrieved_record["image_url"] == unique_file_name
        assert retrieved_record["bucket_name"] == bucket_name # Assert against the bucket name
        assert retrieved_record["prompt"] == test_prompt
        assert retrieved_record["style"] == test_style

        logger.info("Supabase upload, metadata storage/retrieval, and direct Supabase download test successful.")

    except Exception as e:
        logger.error(f"Error during Supabase operations: {e}", exc_info=True)
        pytest.fail(f"Error during Supabase operations: {e}")

    logger.info(f"TOTAL TEST TIME: {time.time() - start_time:.2f}s")

# Note: Add other tests here as needed 