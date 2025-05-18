import httpx
import pytest
import os
import time
import logging

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
async def poll_task_status(task_id: str, service: str):
    status_url = f"{BASE_URL}/tasks/{task_id}/status?service={service.lower()}"
    logger.info(f"Polling {service} task {task_id}...")
    while True:
        try:
            async with httpx.AsyncClient() as client:
                status_response = await client.get(status_url)
                status_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                status_data = status_response.json()
                logger.info(f"Task {task_id} status: {status_data.get('status')}, Progress: {status_data.get('progress')}")

                if status_data.get('status') == 'completed':
                    logger.info(f"Task {task_id} completed.")
                    return status_data.get('result_url')
                elif status_data.get('status') == 'failed':
                    logger.error(f"Task {task_id} failed. Status data: {status_data}")
                    pytest.fail(f"{service.capitalize()} task {task_id} failed.")

            time.sleep(2) # Poll every 2 seconds
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error polling status for task ID {task_id} from service {service}: {e.response.status_code} - {e.response.text}", exc_info=True)
            pytest.fail(f"Failed to poll status for task {task_id} from {service}: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error polling status for task ID {task_id} from service {service}: {e}", exc_info=True)
            pytest.fail(f"Error polling status for task {task_id} from {service}: {e}")

# --- Test Endpoints ---

@pytest.mark.asyncio
async def test_generate_image_to_image(request):
    """Test 1.1: /generate/image-to-image endpoint (OpenAI concepts)."""
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

    files = {'image': (image_filename, image_content, 'image/jpeg')}
    data = {'prompt': prompt, 'style': style}

    logger.info(f"Calling {endpoint} with prompt='{prompt}', style='{style}' and image='{image_filename}'...")
    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, files=files, data=data)
        response.raise_for_status()
        result = response.json()

    logger.info(f"Received response: {result}")

    assert "task_id" in result
    assert "image_urls" in result
    assert isinstance(result["image_urls"], list)
    assert len(result["image_urls"]) > 0

    # Download generated concept images
    for i, url in enumerate(result["image_urls"]):
        await download_file(url, request.node.name, f"concept_{i}.jpg") # Assuming jpg output for concepts


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
    model_url = await poll_task_status(task_id, "tripo")

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
    model_url = await poll_task_status(task_id, "tripo")

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
    model_url = await poll_task_status(task_id, "tripo")

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
    model_url = await poll_task_status(task_id, "tripo")

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
    model_url = await poll_task_status(task_id, "tripo")

    assert model_url is not None
    logger.info(f"Received model URL: {model_url}")

    # Download the generated model
    await download_file(model_url, request.node.name, "model.glb") 