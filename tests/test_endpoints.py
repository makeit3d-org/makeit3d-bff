import httpx
import pytest
import os
import time
import logging
import base64 # Import base64 module
import uuid # Import uuid for generating unique file names

from app.schemas.generation_schemas import ImageToImageRequest
# Import Supabase client functions
from app.supabase_client import get_supabase_client, upload_image_to_storage, create_concept_image_record, download_image_from_storage

BASE_URL = "http://localhost:8000"
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
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            with open(file_path, "wb") as f:
                f.write(response.content)
        logger.info(f"Successfully downloaded {file_name}")
        return file_path
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error downloading file from {url}: {e.response.status_code} - {e.response.text}", exc_info=True)
        pytest.fail(f"Failed to download file from {url}: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Error downloading file from {url}: {e}", exc_info=True)
        pytest.fail(f"Error downloading file from {url}: {e}")

# --- Helper function to poll task status ---
async def poll_task_status(task_id: str, service: str, poll_interval: int = 2, total_timeout: float = 300.0):
    status_url = f"{BASE_URL}/tasks/{task_id}/status?service={service.lower()}"
    logger.info(f"Polling {service} task {task_id} with total timeout {total_timeout}s...")
    start_time = time.time()
    while time.time() - start_time < total_timeout:
        try:
            # Use a shorter timeout for individual polling requests
            async with httpx.AsyncClient(timeout=10.0) as client:
                status_response = await client.get(status_url)
                status_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                status_data = status_response.json()
                logger.info(f"Task {task_id} status: {status_data.get('status')}, Progress: {status_data.get('progress')}")

                if status_data.get('status') == 'completed':
                    logger.info(f"Task {task_id} completed.")
                    # For OpenAI, result is image_data. For Tripo, it's result_url.
                    # Return the entire status data for the test to handle.
                    return status_data
                elif status_data.get('status') == 'failed':
                    logger.error(f"Task {task_id} failed. Status data: {status_data}")
                    pytest.fail(f"{service.capitalize()} task {task_id} failed.")

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

    logger.info(f"Running {request.node.name}...")

    # Download the image from the public URL to include in the multipart request
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_url)
        image_response.raise_for_status()
        image_content = image_response.content
        image_filename = image_url.split("/")[-1] # Extract filename from URL
    
    logger.info(f"INPUT IMAGE DOWNLOAD: {time.time() - start_time:.2f}s")

    files = {'image': (image_filename, image_content, 'image/jpeg')}
    data = {'prompt': prompt, 'style': style, 'n': 1}

    logger.info(f"Calling {endpoint} with prompt='{prompt}', style='{style}', image='{image_filename}' and n=1...")
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
    task_result_data = await poll_task_status(task_id, "openai", poll_interval=5, total_timeout=180.0) # Increased timeout
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
    endpoint = f"{BASE_URL}/generate/text-to-model"
    prompt = "A violet colored cartoon flying elephant with big flapping ears"

    logger.info(f"Running {request.node.name}...")

    request_data = {"prompt": prompt, "texture": True}

    logger.info(f"Calling {endpoint} with prompt='{prompt}'...")
    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()

    logger.info(f"Received response: {result}")

    assert "task_id" in result
    task_id = result["task_id"]
    logger.info(f"Received Tripo AI task_id: {task_id}")

    # Poll for task completion and get result URL
    model_url_data = await poll_task_status(task_id, "tripo", total_timeout=300.0) # Set a total timeout for Tripo polling

    # Extract model_url from the result_url field
    model_url = model_url_data.get('result_url')

    assert model_url is not None
    logger.info(f"Received model URL: {model_url}")

    # Download the generated model
    await download_file(model_url, request.node.name, "model.glb")


@pytest.mark.asyncio
async def test_generate_from_concept(request):
    """Test 2.2: /generate/select-concept endpoint (Tripo AI from OpenAI concept)."""
    # This test depends on the output of test_1_1_image_to_image.
    # You need to run test_1_1 first and get a valid concept image URL and task ID.
    # For automated testing, you might chain these or retrieve a known good concept URL/task ID.
    # For this implementation, I'll use placeholders and skip the test if they are not updated.
    select_concept_endpoint = f"{BASE_URL}/generate/select-concept"

    # --- PLACEHOLDERS --- Update these with actual values after running test_1_1 ---
    concept_image_url = os.environ.get("TEST_2_2_CONCEPT_IMAGE_URL", "YOUR_CONCEPT_IMAGE_URL") # Get from env var or placeholder
    concept_task_id = os.environ.get("TEST_2_2_CONCEPT_TASK_ID", "YOUR_CONCEPT_TASK_ID") # Get from env var or placeholder
    # ---------------------------------------------------------------------------

    if concept_image_url == "YOUR_CONCEPT_IMAGE_URL" or concept_task_id == "YOUR_CONCEPT_TASK_ID":
         logger.info(f"Skipping {request.node.name}: PLACEHOLDERS not updated. Run test_1_1 and update environment variables TEST_2_2_CONCEPT_IMAGE_URL and TEST_2_2_CONCEPT_TASK_ID, or update the placeholders in the test file.")
         pytest.skip("Requires a valid concept image URL and task ID from test_1_1.")

    logger.info(f"Running {request.node.name} with concept URL: {concept_image_url}")

    request_data = {
        "concept_task_id": concept_task_id, # Use the dummy or real concept task ID
        "selected_image_url": concept_image_url,
        "texture": True # Assuming texture is true for this test
    }

    logger.info(f"Calling {select_concept_endpoint} with selected_image_url='{concept_image_url}'...")
    async with httpx.AsyncClient() as client:
        response = await client.post(select_concept_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()

    logger.info(f"Received response: {result}")

    assert "task_id" in result
    task_id = result["task_id"]
    logger.info(f"Received Tripo AI task_id from concept: {task_id}")

    # Poll for task completion and get result URL
    model_url_data = await poll_task_status(task_id, "tripo", total_timeout=300.0)

    # Extract model_url from the result_url field
    model_url = model_url_data.get('result_url')

    assert model_url is not None
    logger.info(f"Received model URL: {model_url}")

    # Download the generated model
    await download_file(model_url, request.node.name, "model.glb")


@pytest.mark.asyncio
async def test_generate_image_to_model_texture(request):
    """Test 3.1 (texture): /generate/image-to-model endpoint (Tripo AI multiview) using concept output."""
    # This test uses the output concept image URL from test_1_1_image_to_image as input.
    # Similar to test_2_2, you need to run test_1_1 first and get a valid concept image URL.
    # For this implementation, I'll use a placeholder and skip the test if it's not updated.
    image_to_model_endpoint = f"{BASE_URL}/generate/image-to-model"

    # --- PLACEHOLDER --- Update this with an actual concept image URL after running test_1_1 ---
    concept_image_url = os.environ.get("TEST_3_1_CONCEPT_IMAGE_URL", "YOUR_CONCEPT_IMAGE_URL") # Get from env var or placeholder
    # ---------------------------------------------------------------------------------------

    if concept_image_url == "YOUR_CONCEPT_IMAGE_URL":
         logger.info(f"Skipping {request.node.name}: PLACEHOLDER not updated. Run test_1_1 and update environment variable TEST_3_1_CONCEPT_IMAGE_URL, or update the placeholder in the test file.")
         pytest.skip("Requires a valid concept image URL from test_1_1.")

    logger.info(f"Running {request.node.name} with input image URL: {concept_image_url}")

    request_data = {
        "image_urls": [concept_image_url], # Using the concept image URL as input for multiview (assuming Tripo handles single image input here too)
        "prompt": "3D model from concept", # Optional prompt
        "style": "", # Optional style
        "texture": True
    }

    logger.info(f"Calling {image_to_model_endpoint} with image_urls='{request_data["image_urls"]}'...")
    async with httpx.AsyncClient() as client:
        response = await client.post(image_to_model_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()

    logger.info(f"Received response: {result}")

    assert "task_id" in result
    task_id = result["task_id"]
    logger.info(f"Received Tripo AI task_id: {task_id}")

    # Poll for task completion and get result URL
    model_url_data = await poll_task_status(task_id, "tripo", total_timeout=300.0)

    # Extract model_url from the result_url field
    model_url = model_url_data.get('result_url')

    assert model_url is not None
    logger.info(f"Received model URL: {model_url}")

    # Download the generated model
    await download_file(model_url, request.node.name, "model.glb")


@pytest.mark.asyncio
async def test_generate_image_to_model_no_texture(request):
    """Test 3.1 (no texture): /generate/image-to-model endpoint (Tripo AI multiview) using concept output."""
    # This test also uses the output concept image URL from test_1_1_image_to_image as input.
    # Similar to test_3_1_texture, you need to run test_1_1 first and get a valid concept image URL.
    # For this implementation, I'll use a placeholder and skip the test if it's not updated.
    image_to_model_endpoint = f"{BASE_URL}/generate/image-to-model"

    # --- PLACEHOLDER --- Update this with an actual concept image URL after running test_1_1 ---
    concept_image_url = os.environ.get("TEST_3_1_CONCEPT_IMAGE_URL", "YOUR_CONCEPT_IMAGE_URL") # Get from env var or placeholder
    # ---------------------------------------------------------------------------------------

    if concept_image_url == "YOUR_CONCEPT_IMAGE_URL":
         logger.info(f"Skipping {request.node.name}: PLACEHOLDER not updated. Run test_1_1 and update environment variable TEST_3_1_CONCEPT_IMAGE_URL, or update the placeholder in the test file.")
         pytest.skip("Requires a valid concept image URL from test_1_1.")

    logger.info(f"Running {request.node.name} with input image URL: {concept_image_url}")

    request_data = {
        "image_urls": [concept_image_url], # Using the concept image URL as input for multiview (assuming Tripo handles single image input here too)
        "prompt": "3D model from concept", # Optional prompt
        "style": "", # Optional style
        "texture": False # Set texture to False for this test
    }

    logger.info(f"Calling {image_to_model_endpoint} with image_urls='{request_data["image_urls"]}'...")
    async with httpx.AsyncClient() as client:
        response = await client.post(image_to_model_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()

    logger.info(f"Received response: {result}")

    assert "task_id" in result
    task_id = result["task_id"]
    logger.info(f"Received Tripo AI task_id: {task_id}")

    # Poll for task completion and get result URL
    model_url_data = await poll_task_status(task_id, "tripo", total_timeout=300.0)

    # Extract model_url from the result_url field
    model_url = model_url_data.get('result_url')

    assert model_url is not None
    logger.info(f"Received model URL: {model_url}")

    # Download the generated model
    await download_file(model_url, request.node.name, "model.glb")


@pytest.mark.asyncio
async def test_generate_sketch_to_model(request):
    """Test 4.1: /generate/sketch-to-model endpoint (Tripo AI single image)."""
    endpoint = f"{BASE_URL}/generate/sketch-to-model"
    sketch_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat.jpg"
    prompt = "Create a photorealistic 3D rendering of the subject depicted in the provided sketch. Preserve the original proportions, geometry, and quirks of the drawing, no matter how unrealistic or awkward they are. The result should look like the sketch was literally brought to life in the real world, with realistic textures, lighting, and surroundings. The rendering should show what it would look like if the drawing existed as a physical object or creature."
    style = None # No style for this test

    logger.info(f"Running {request.node.name} with sketch image URL: {sketch_image_url}")

    request_data = {
        "image_url": sketch_image_url,
        "prompt": prompt,
        "style": style,
        "texture": True # Assuming texture is true for this test
    }

    logger.info(f"Calling {endpoint} with image_url='{sketch_image_url}' and prompt='{prompt}'...")
    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()

    logger.info(f"Received response: {result}")

    assert "task_id" in result
    task_id = result["task_id"]
    logger.info(f"Received Tripo AI task_id: {task_id}")

    # Poll for task completion and get result URL
    model_url_data = await poll_task_status(task_id, "tripo", total_timeout=300.0)

    # Extract model_url from the result_url field
    model_url = model_url_data.get('result_url')

    assert model_url is not None
    logger.info(f"Received model URL: {model_url}")

    # Download the generated model
    await download_file(model_url, request.node.name, "model.glb")


@pytest.mark.asyncio
async def test_supabase_upload_and_metadata(request):
    """Simple test to upload an image to Supabase Storage and save metadata to the database."""
    logger.info(f"Running {request.node.name}...")

    # 1. Download a small public image
    image_to_download_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"
    logger.info(f"Downloading image from {image_to_download_url} for Supabase test.")
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_to_download_url)
        image_response.raise_for_status()
        image_content = image_response.content

    # 2. Upload the image to Supabase Storage
    # Use .jpg extension to match the downloaded file type
    unique_file_name = f"test_uploads/{uuid.uuid4()}.jpg"
    logger.info(f"Uploading image to Supabase Storage: {unique_file_name}")
    uploaded_url = await upload_image_to_storage(unique_file_name, image_content)
    logger.info(f"Image uploaded to: {uploaded_url}")

    assert uploaded_url is not None
    # Assertions for database record verification start here

    # 3. Define metadata and save to the database
    test_task_id = f"test-task-{uuid.uuid4()}"
    test_prompt = "This is a test upload image."
    test_style = "None"
    bucket_name = "concept-images" # Use the correct bucket name

    logger.info(f"Saving metadata to database for task ID: {test_task_id} with image_url: {unique_file_name}")

    # Pass the file path (uploaded_url) and bucket name to the create_concept_image_record function
    await create_concept_image_record(test_task_id, unique_file_name, bucket_name, test_prompt, test_style) # Pass unique_file_name (file_path)
    logger.info(f"Metadata record created.")

    # 4. Download the image directly from Supabase Storage using the download_image_from_storage function
    logger.info(f"Downloading image directly from Supabase Storage: {bucket_name}/{unique_file_name}")
    downloaded_image_data = await download_image_from_storage(unique_file_name, bucket_name)
    logger.info(f"Image data downloaded directly from Supabase. Size: {len(downloaded_image_data)} bytes.")

    # Basic assertion to check if downloaded data is not empty
    assert downloaded_image_data is not None and len(downloaded_image_data) > 0, "Downloaded image data is empty or None."

    # 5. Retrieve the metadata from the database and verify
    supabase = get_supabase_client()
    logger.info(f"Retrieving metadata from database for task ID: {test_task_id}")
    try:
        response = supabase.table("concept_images").select("*").eq("task_id", test_task_id).execute()
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

    # Optional: Clean up the uploaded file and database record
    # This is good practice for tests, but might add complexity. Skipping for now.
    # try:
    #     # Delete from storage
    #     storage_delete_response = supabase.storage.from_("concept_images").remove([unique_file_name])
    #     logger.info(f"Storage cleanup response: {storage_delete_response}")
    #     # Delete from database
    #     db_delete_response = supabase.table("concept_images").delete().eq("task_id", test_task_id).execute()
    #     logger.info(f"Database cleanup response: {db_delete_response}")
    # except Exception as cleanup_e:
    #      logger.warning(f"Error during test cleanup: {cleanup_e}", exc_info=True)

# Note: Add other tests here as needed 