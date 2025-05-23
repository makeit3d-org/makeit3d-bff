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
from app.supabase_client import get_supabase_client, download_image_from_storage, create_signed_url
import app.supabase_handler as supabase_handler # Add supabase_handler import
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

                if status_data.get('status') == 'complete':
                    logger.info(f"Task {task_id} complete.")
                    
                    # For Tripo tasks, ensure we have an asset_url (model_url)
                    if service.lower() == 'tripoai' and not status_data.get('asset_url'):
                        # If there's no asset_url but the task is complete, poll one more time
                        # Sometimes the model_url isn't immediately available
                        logger.warning(f"Task {task_id} marked as complete but missing asset_url. Polling once more...")
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
                if service.lower() == 'tripoai' and status_data.get('progress') == 100:
                    if status_data.get('asset_url'):
                        logger.info(f"Task {task_id} at 100% with asset_url. Considering complete.")
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
    image_to_upload_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"
    prompt = "Transform me into a toy action figure. Make it look like I am made out of plastic. Make sure to still make it look like me as much as possible. Include my whole body with no background, surroundings or detached objects."
    style = "Cartoonish, cute but still realistic."
    background = "transparent"
    client_task_id = f"test-i2i-{uuid.uuid4()}" # Client-generated task_id

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    # 1. Download the public image
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_to_upload_url)
        image_response.raise_for_status()
        image_content = image_response.content
        original_filename = image_to_upload_url.split("/")[-1]
    
    logger.info(f"INPUT IMAGE DOWNLOADED: {original_filename}")

    # 2. Upload the image to Supabase Storage (simulating client upload)
    # Use .jpg extension to match the downloaded file type
    supabase_image_path = f"test_inputs/image-to-image/{client_task_id}/{original_filename}"
    logger.info(f"Uploading image to Supabase Storage: {supabase_image_path}")
    
    # upload_asset_to_storage returns the full URL 
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/image-to-image", 
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/jpeg"
    )
    logger.info(f"Image uploaded to Supabase URL: {input_supabase_url}")

    # No need to construct URL since upload_asset_to_storage returns it
    logger.info(f"Using Supabase input URL: {input_supabase_url}")
    
    # 3. Call BFF endpoint with Supabase URL
    request_data = {
        "task_id": client_task_id,
        "input_image_asset_url": input_supabase_url,
        "prompt": prompt,
        "style": style,
        "n": 1,
        "background": background
    }

    logger.info(f"Calling {endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data) # Send JSON payload
        response.raise_for_status()
        result = response.json()
        logger.info(f"API RESPONSE TIME: {time.time() - api_call_start:.2f}s")

    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result # Celery task_id
    celery_task_id = result["celery_task_id"]
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Poll for task completion and get the result data
    logger.info(f"Polling for completion of OpenAI task {celery_task_id}...")
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "openai", poll_interval=2, total_timeout=180.0)
    logger.info(f"TASK PROCESSING TIME (includes OpenAI generation + Supabase storage): {time.time() - polling_start:.2f}s")

    # Verify that the response contains the expected asset URL
    assert task_result_data.get('status') == 'complete'
    assert 'asset_url' in task_result_data
    asset_url = task_result_data['asset_url'] # This is the Supabase URL
    
    # For image-to-image, we expect at least one generated concept
    assert asset_url is not None
    logger.info(f"Received concept image Supabase URL: {asset_url}")

    # Download the generated concept image
    await download_file(asset_url, request.node.name, "concept_image.png")

    expected_n = request_data.get('n', 1)
    assert isinstance(asset_url, str)
    assert len(asset_url) > 0

    logger.info(f"TOTAL TEST TIME: {time.time() - start_time:.2f}s")


@pytest.mark.asyncio
async def test_generate_text_to_model(request):
    """Test 2.1: /generate/text-to-model endpoint (Tripo AI direct)."""
    start_time = time.time()
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/text-to-model"
    prompt = "A violet colored cartoon flying elephant with big flapping ears"
    client_task_id = f"test-t2m-{uuid.uuid4()}" # Client-generated task_id

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    request_data = {
        "task_id": client_task_id,
        "prompt": prompt,
        "texture_quality": "standard" # Added to match Pydantic schema (assuming it's 'texture_quality')
                                     # Or it could be just "texture": True if that's the schema. Let's assume texture_quality for now.
                                     # Will need to verify against actual Pydantic schema for TextToModelRequest.
                                     # Based on API_REFACTOR.md, it's "texture_quality": "standard" | "detailed"
    }

    logger.info(f"Calling {endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"API RESPONSE TIME: {time.time() - api_call_start:.2f}s")

    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result # This is the Celery task_id
    celery_task_id = result["celery_task_id"]
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Poll for task completion and get result URL
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "tripoai", total_timeout=300.0)
    logger.info(f"TASK PROCESSING TIME: {time.time() - polling_start:.2f}s")
    logger.info(f"Full task_result_data: {task_result_data}")

    model_url = task_result_data.get('asset_url') # Expecting 'asset_url' based on TaskStatusResponse schema

    assert model_url is not None, f"Model asset_url not found in response: {task_result_data}"
    logger.info(f"Received model Supabase URL: {model_url}")

    # Download the generated model
    download_start = time.time()
    model_file_path = await download_file(model_url, request.node.name, "model.glb")
    logger.info(f"MODEL DOWNLOAD TIME: {time.time() - download_start:.2f}s")
    logger.info(f"Model downloaded to: {model_file_path}")
    
    assert os.path.exists(model_file_path)
    assert os.path.getsize(model_file_path) > 0
    
    logger.info(f"TOTAL TEST TIME: {time.time() - start_time:.2f}s")


@pytest.mark.asyncio
async def test_generate_image_to_model(request):
    """Test 3.0: /generate/image-to-model endpoint (Tripo AI) using a client-provided Supabase image URL."""
    start_time = time.time()
    logger.info(f"TEST START: {start_time}")
    
    image_to_model_endpoint = f"{BASE_URL}/generate/image-to-model"
    client_task_id = f"test-i2m-{uuid.uuid4()}"

    # Simulate client uploading an image to their Supabase and providing the URL
    image_to_upload_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-concept.png" # Using a concept-like image

    logger.info(f"Running {request.node.name} for task_id: {client_task_id} with input image URL: {image_to_upload_url}")

    # 1. Download the public image
    async with httpx.AsyncClient() as client:
        img_response = await client.get(image_to_upload_url)
        img_response.raise_for_status()
        image_content = img_response.content
        original_filename = image_to_upload_url.split("/")[-1]
    logger.info(f"INPUT IMAGE DOWNLOADED: {original_filename}")

    # 2. Upload image to Supabase (simulating client's asset)
    supabase_image_path = f"test_inputs/image-to-model/{client_task_id}/{original_filename}"
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/image-to-model",
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/png" if original_filename.endswith('.png') else "image/jpeg"
    )
    logger.info(f"Input image uploaded to Supabase, URL: {input_supabase_url}")

    request_data = {
        "task_id": client_task_id,
        "input_image_asset_urls": [input_supabase_url], 
        "prompt": "3D model from image",
        "texture_quality": "standard" # Match Pydantic ImageToModelRequest
    }

    logger.info(f"Calling {image_to_model_endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(image_to_model_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"API RESPONSE TIME: {time.time() - api_call_start:.2f}s")

    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result # Celery task_id
    celery_task_id = result["celery_task_id"]
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Poll for task completion
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "tripoai", total_timeout=300.0)
    logger.info(f"TASK PROCESSING TIME: {time.time() - polling_start:.2f}s")

    model_url = task_result_data.get('asset_url') # Expecting 'asset_url'
    assert model_url is not None, f"Model asset_url not found in response: {task_result_data}"
    logger.info(f"Received model Supabase URL: {model_url}")

    # Download the generated model
    download_start = time.time()
    await download_file(model_url, request.node.name, "model.glb")
    logger.info(f"MODEL DOWNLOAD TIME: {time.time() - download_start:.2f}s")
    
    logger.info(f"TOTAL TEST TIME: {time.time() - start_time:.2f}s")


@pytest.mark.asyncio
async def test_generate_sketch_to_model(request):
    """Test 4.1: /generate/sketch-to-model endpoint using a client-provided Supabase sketch URL."""
    start_time = time.time()
    logger.info(f"TEST START: {start_time}")
    client_task_id = f"test-s2m-{uuid.uuid4()}"
    
    sketch_to_model_endpoint = f"{BASE_URL}/generate/sketch-to-model"
    
    # 1. Simulate client having a sketch image in their Supabase.
    # For the test, we download a public sketch, then upload it to our test Supabase area.
    public_sketch_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat.jpg"
    logger.info(f"Running {request.node.name} for task_id: {client_task_id}. Using public sketch: {public_sketch_url}")

    async with httpx.AsyncClient() as client:
        sketch_response = await client.get(public_sketch_url)
        sketch_response.raise_for_status()
        sketch_content = sketch_response.content
        original_sketch_filename = public_sketch_url.split("/")[-1]
    logger.info(f"INPUT SKETCH DOWNLOADED: {original_sketch_filename}")

    supabase_sketch_path = f"test_inputs/sketch-to-model/{client_task_id}/{original_sketch_filename}"
    input_sketch_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/sketch-to-model",
        file_name=original_sketch_filename,
        asset_data=sketch_content,
        content_type="image/jpeg" if original_sketch_filename.endswith('.jpg') else "image/png"
    )
    logger.info(f"Input sketch uploaded to Supabase, URL: {input_sketch_supabase_url}")
    
    # 2. Call BFF endpoint with the Supabase URL of the sketch
    request_data = {
        "task_id": client_task_id,
        "input_sketch_asset_url": input_sketch_supabase_url,
        "prompt": "A 3D model of the provided sketch.",
        "style": "Cartoonish", # Optional, ensure it aligns with SketchToModelRequest if it has it
        "texture_quality": "standard" # Match Pydantic SketchToModelRequest
    }
    
    logger.info(f"Calling {sketch_to_model_endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        tripo_api_call_start = time.time()
        response = await client.post(sketch_to_model_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"API RESPONSE TIME (Tripo): {time.time() - tripo_api_call_start:.2f}s")
    
    logger.info(f"Received response from BFF: {result}")
    
    assert "celery_task_id" in result # Celery task_id
    celery_task_id = result["celery_task_id"]
    logger.info(f"Received Celery task_id: {celery_task_id}")
    
    # Poll for task completion
    tripo_polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "tripoai", total_timeout=300.0)
    logger.info(f"TRIPO TASK PROCESSING TIME: {time.time() - tripo_polling_start:.2f}s")
    
    model_url = task_result_data.get('asset_url') # Expecting 'asset_url'
    assert model_url is not None, f"Model asset_url not found in response: {task_result_data}"
    logger.info(f"Received model Supabase URL: {model_url}")
    
    # Download the generated model
    model_download_start = time.time()
    model_file_path = await download_file(model_url, request.node.name, "model_from_sketch.glb")
    logger.info(f"MODEL DOWNLOAD TIME: {time.time() - model_download_start:.2f}s")
    logger.info(f"Model downloaded to: {model_file_path}")
    
    logger.info(f"TOTAL TEST TIME: {time.time() - start_time:.2f}s")


@pytest.mark.asyncio
async def test_supabase_upload_and_metadata(request):
    """Test to upload an image to Supabase Storage and save metadata with the new schema."""
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

    # 2. Upload the image to Supabase Storage (using makeit3d-app-assets bucket)
    test_task_id = f"test-task-{uuid.uuid4()}"
    unique_file_name = f"test_concept.jpg"  # Changed back to JPG to match downloaded file
    logger.info(f"Uploading image to Supabase Storage: concepts/{test_task_id}/{unique_file_name}")
    upload_start = time.time()
    full_asset_url = await supabase_handler.upload_asset_to_storage(
        task_id=test_task_id,
        asset_type_plural="concepts",
        file_name=unique_file_name,
        asset_data=image_content,
        content_type="image/jpeg"  # Changed back to JPEG
    )
    logger.info(f"Image uploaded to: {full_asset_url}")
    logger.info(f"UPLOAD TIME: {time.time() - upload_start:.2f}s")

    assert full_asset_url is not None

    # 3. The asset URL is already the full URL from upload_asset_to_storage
    logger.info(f"Full asset URL: {full_asset_url}")

    # 4. Create a metadata record in the concept_images table with new schema
    test_prompt = "This is a test upload image."
    test_style = "test_style"
    
    logger.info(f"Creating concept_images record for task_id: {test_task_id}")
    db_start = time.time()
    
    supabase = get_supabase_client()
    
    # Insert record with new schema (using simplified status system)
    concept_record = {
        "task_id": test_task_id,
        "user_id": None,  # For test purposes, using None (would be actual user_id in real app)
        "source_input_asset_id": None,  # No source input for this test
        "prompt": test_prompt,
        "style": test_style,
        "asset_url": full_asset_url,  # Full Supabase URL
        "status": "complete",  # Using simplified status system
        "ai_service_task_id": f"test-task-{uuid.uuid4()}",
        "metadata": {"test": True, "uploaded_by": "test_suite"}
    }
    
    try:
        response = supabase.table("concept_images").insert(concept_record).execute()
        logger.info(f"Concept image record created: {response.data}")
        logger.info(f"DB WRITE TIME: {time.time() - db_start:.2f}s")
        
        # Verify the insert was successful
        assert len(response.data) == 1, "Expected exactly one record to be created."
        created_record = response.data[0]
        
    except Exception as e:
        logger.error(f"Error creating concept_images record: {e}", exc_info=True)
        pytest.fail(f"Error creating concept_images record: {e}")

    # 5. Download the image directly from Supabase Storage using authenticated access
    logger.info(f"Downloading image from Supabase using authenticated fetch_asset_from_storage")
    supabase_dl_start = time.time()
    
    # Use authenticated download instead of public HTTP GET
    downloaded_image_data = await supabase_handler.fetch_asset_from_storage(full_asset_url)
        
    logger.info(f"Image data downloaded from Supabase. Size: {len(downloaded_image_data)} bytes.")
    logger.info(f"SUPABASE DOWNLOAD TIME: {time.time() - supabase_dl_start:.2f}s")

    # Basic assertion to check if downloaded data is not empty
    assert downloaded_image_data is not None and len(downloaded_image_data) > 0, "Downloaded image data is empty or None."
    
    # Verify the downloaded content matches the original
    assert len(downloaded_image_data) == len(image_content), "Downloaded image size doesn't match original"

    # 6. Retrieve the metadata from the database and verify with new schema
    logger.info(f"Retrieving metadata from concept_images table for task_id: {test_task_id}")
    db_query_start = time.time()
    try:
        response = supabase.table("concept_images").select("*").eq("task_id", test_task_id).execute()
        logger.info(f"DATABASE QUERY TIME: {time.time() - db_query_start:.2f}s")
        logger.info(f"Database query response data: {response.data}")
        
        # Check for errors more robustly
        assert not hasattr(response, 'error') or response.error is None, "Database query failed."
        assert len(response.data) == 1, "Expected exactly one record for the task_id."

        retrieved_record = response.data[0]

        # Verify all fields with new schema
        assert retrieved_record["task_id"] == test_task_id
        assert retrieved_record["asset_url"] == full_asset_url
        assert retrieved_record["prompt"] == test_prompt
        assert retrieved_record["style"] == test_style
        assert retrieved_record["status"] == "complete"  # Verify simplified status
        assert retrieved_record["metadata"]["test"] == True
        
        logger.info("New schema verification successful:")
        logger.info(f"  - task_id: {retrieved_record['task_id']}")
        logger.info(f"  - asset_url: {retrieved_record['asset_url']}")
        logger.info(f"  - status: {retrieved_record['status']}")
        logger.info(f"  - metadata: {retrieved_record['metadata']}")

        logger.info("Supabase upload, metadata storage/retrieval with new schema test successful.")

    except Exception as e:
        logger.error(f"Error during Supabase operations: {e}", exc_info=True)
        pytest.fail(f"Error during Supabase operations: {e}")

    logger.info(f"TOTAL TEST TIME: {time.time() - start_time:.2f}s")


@pytest.mark.asyncio
async def test_generate_multiview_to_model(request):
    """Test 3.1: /generate/image-to-model endpoint with multiple images (multiview mode)."""
    start_time = time.time()
    logger.info(f"TEST START: {start_time}")
    
    image_to_model_endpoint = f"{BASE_URL}/generate/image-to-model"
    client_task_id = f"test-multiview-{uuid.uuid4()}"

    # URLs for multiview images in [front, left, back, right] order as per API spec
    multiview_image_urls = [
        "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-front-concept.png",  # front
        "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-left-concept.png",   # left
        "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-back--concept.png",  # back
        "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-right-concept.png", # right
    ]

    logger.info(f"Running {request.node.name} for task_id: {client_task_id} with {len(multiview_image_urls)} images")
    logger.info(f"Multiview image ordering: [front, left, back, right] - testing full 4-view multiview")

    # 1. Download and upload all images to Supabase (simulating client's multiview assets)
    input_supabase_urls = []
    view_names = ["front", "left", "back", "right"]
    
    for i, image_url in enumerate(multiview_image_urls):
        async with httpx.AsyncClient() as client:
            img_response = await client.get(image_url)
            img_response.raise_for_status()
            image_content = img_response.content
            original_filename = f"{view_names[i]}_{image_url.split('/')[-1]}"
        
        logger.info(f"INPUT IMAGE DOWNLOADED: {original_filename} for {view_names[i]} view")

        # Upload to Supabase with view name in path
        supabase_image_path = f"test_inputs/multiview-to-model/{client_task_id}/{original_filename}"
        input_supabase_url = await supabase_handler.upload_asset_to_storage(
            task_id=client_task_id,
            asset_type_plural="test_inputs/multiview-to-model",
            file_name=original_filename,
            asset_data=image_content,
            content_type="image/png" if original_filename.endswith('.png') else "image/jpeg"
        )
        input_supabase_urls.append(input_supabase_url)
        logger.info(f"✓ {view_names[i]} view uploaded to Supabase: {input_supabase_url}")

    logger.info(f"All {len(input_supabase_urls)} images uploaded. Calling multiview endpoint...")

    request_data = {
        "task_id": client_task_id,
        "input_image_asset_urls": input_supabase_urls,  # Multiple URLs trigger multiview mode
        "prompt": "High quality 3D model from multiview images",
        "texture_quality": "detailed",  # Use higher quality for multiview
        "pbr": True  # Enable PBR for better results
    }

    logger.info(f"Calling {image_to_model_endpoint} with multiview JSON data: {request_data}")
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(image_to_model_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"API RESPONSE TIME: {time.time() - api_call_start:.2f}s")

    logger.info(f"Received multiview response: {result}")

    assert "celery_task_id" in result # Celery task_id
    celery_task_id = result["celery_task_id"]
    logger.info(f"Received Celery task_id for multiview generation: {celery_task_id}")

    # Poll for task completion (multiview may take longer)
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "tripoai", total_timeout=450.0)  # Longer timeout for multiview
    logger.info(f"MULTIVIEW TASK PROCESSING TIME: {time.time() - polling_start:.2f}s")

    model_url = task_result_data.get('asset_url') # Expecting 'asset_url'
    assert model_url is not None, f"Model asset_url not found in multiview response: {task_result_data}"
    logger.info(f"Received multiview model Supabase URL: {model_url}")

    # Download the generated multiview model
    download_start = time.time()
    await download_file(model_url, request.node.name, "multiview_model.glb")
    logger.info(f"MULTIVIEW MODEL DOWNLOAD TIME: {time.time() - download_start:.2f}s")
    
    logger.info(f"TOTAL MULTIVIEW TEST TIME: {time.time() - start_time:.2f}s")

# Note: Add other tests here as needed 