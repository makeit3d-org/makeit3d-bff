import httpx
import pytest
import os
import time

BASE_URL = "http://localhost:8000"
OUTPUTS_DIR = "./tests/outputs"

# Ensure the outputs directory exists
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# --- Helper function to download files ---
async def download_file(url: str, filename: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        file_path = os.path.join(OUTPUTS_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(response.content)
        print(f"Downloaded {url} to {file_path}")

# --- Helper function to poll Tripo AI task status ---
async def poll_tripo_task(task_id: str):
    status_url = f"{BASE_URL}/tasks/{task_id}/status"
    print(f"Polling Tripo task {task_id}...")
    while True:
        async with httpx.AsyncClient() as client:
            status_response = await client.get(status_url, params={'service': 'tripo'})
            status_response.raise_for_status()
            status_data = status_response.json()
            print(f"Task {task_id} status: {status_data['status']}, Progress: {status_data.get('progress')}")

            if status_data['status'] == 'completed':
                print(f"Task {task_id} completed.")
                return status_data.get('result_url')
            elif status_data['status'] == 'failed':
                print(f"Task {task_id} failed.")
                pytest.fail(f"Tripo AI task {task_id} failed.")

            time.sleep(5) # Poll every 5 seconds

# --- Test Endpoints ---

@pytest.mark.asyncio
async def test_generate_image_to_image():
    """Test the /generate/image-to-image endpoint (OpenAI concepts)."""
    endpoint = f"{BASE_URL}/generate/image-to-image"
    # For testing multipart/form-data, you need a local image file.
    # Replace 'path/to/your/test_image.png' with a valid path to a test image.
    test_image_path = "./tests/test_image.png" # Placeholder: Create a dummy file or use a real one
    if not os.path.exists(test_image_path):
        # Create a dummy file if it doesn't exist
        with open(test_image_path, "wb") as f:
            f.write(b"dummy image data")
        print(f"Created dummy test image at {test_image_path}")

    files = {'image': ('test_image.png', open(test_image_path, 'rb'))}
    data = {'prompt': 'a futuristic car', 'style': 'cartoon'}

    print(f"Calling {endpoint}...")
    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, files=files, data=data)
        response.raise_for_status()
        result = response.json()

    assert "task_id" in result
    assert "image_urls" in result
    assert isinstance(result["image_urls"], list)
    assert len(result["image_urls"]) > 0

    print(f"Received task_id: {result['task_id']}")
    print(f"Received image_urls: {result['image_urls']}")

    # Download generated concept images
    for i, url in enumerate(result["image_urls"]):
        await download_file(url, f"concept_{i}.png")


@pytest.mark.asyncio
async def test_generate_text_to_model():
    """Test the /generate/text-to-model endpoint (Tripo AI)."""
    endpoint = f"{BASE_URL}/generate/text-to-model"
    request_data = {"prompt": "a small house", "texture": True}

    print(f"Calling {endpoint} with {request_data}...")
    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()

    assert "task_id" in result
    task_id = result["task_id"]
    print(f"Received Tripo AI task_id: {task_id}")

    # Poll for task completion
    model_url = await poll_tripo_task(task_id)

    assert model_url is not None
    print(f"Received model URL: {model_url}")

    # Download the generated model
    await download_file(model_url, f"text_to_model_{task_id}.glb")


@pytest.mark.asyncio
async def test_generate_image_to_model():
    """Test the /generate/image-to-model endpoint (Tripo AI multiview)."""
    endpoint = f"{BASE_URL}/generate/image-to-model"
    # For image-to-model (multiview), you need URLs of input images.
    # Replace with actual publicly accessible image URLs for testing.
    request_data = {
        "image_urls": [
            "https://example.com/image1.png", # Placeholder URL
            "https://example.com/image2.png"  # Placeholder URL
        ],
        "prompt": "a chair",
        "texture": True
    }
    print("NOTE: Replace placeholder image_urls with actual publicly accessible URLs for this test.")

    print(f"Calling {endpoint} with {request_data}...")
    async with httpx.AsyncClient() as client:
        # Note: Tripo AI needs to be able to access these URLs.
        # Using dummy URLs here will result in Tripo AI errors.
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()

    assert "task_id" in result
    task_id = result["task_id"]
    print(f"Received Tripo AI task_id: {task_id}")

    # Poll for task completion
    # NOTE: This will likely fail with dummy URLs above.
    model_url = await poll_tripo_task(task_id)

    assert model_url is not None
    print(f"Received model URL: {model_url}")

    # Download the generated model
    await download_file(model_url, f"image_to_model_{task_id}.glb")


@pytest.mark.asyncio
async def test_generate_sketch_to_model():
    """Test the /generate/sketch-to-model endpoint (Tripo AI single image)."""
    endpoint = f"{BASE_URL}/generate/sketch-to-model"
     # For sketch-to-model, you need a URL of the input sketch image.
    # Replace with an actual publicly accessible sketch image URL for testing.
    request_data = {
        "image_url": "https://example.com/sketch.png", # Placeholder URL
        "prompt": "a simple sketch",
        "texture": True
    }
    print("NOTE: Replace placeholder image_url with an actual publicly accessible URL for this test.")

    print(f"Calling {endpoint} with {request_data}...")
    async with httpx.AsyncClient() as client:
        # Note: Tripo AI needs to be able to access this URL.
        # Using a dummy URL here will result in Tripo AI errors.
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()

    assert "task_id" in result
    task_id = result["task_id"]
    print(f"Received Tripo AI task_id: {task_id}")

    # Poll for task completion
    # NOTE: This will likely fail with a dummy URL above.
    model_url = await poll_tripo_task(task_id)

    assert model_url is not None
    print(f"Received model URL: {model_url}")

    # Download the generated model
    await download_file(model_url, f"sketch_to_model_{task_id}.glb")


@pytest.mark.asyncio
async def test_generate_refine_model():
    """Test the /generate/refine-model endpoint (Tripo AI)."""
    endpoint = f"{BASE_URL}/generate/refine-model"
    # To test refine-model, you need a task_id of a *draft* model that was successfully generated.
    # This requires successfully running one of the initial generation tests first and getting a task_id.
    # Replace 'YOUR_DRAFT_TASK_ID' with an actual task ID of a successfully generated draft model.
    draft_task_id = "YOUR_DRAFT_TASK_ID" # Placeholder
    print("NOTE: Replace YOUR_DRAFT_TASK_ID with an actual task ID of a successfully generated draft model.")

    if draft_task_id == "YOUR_DRAFT_TASK_ID":
        print("Skipping refine model test: YOUR_DRAFT_TASK_ID is a placeholder.")
        pytest.skip("Requires a valid draft model task ID.")

    request_data = {"draft_model_task_id": draft_task_id}

    print(f"Calling {endpoint} with {request_data}...")
    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()

    assert "task_id" in result
    task_id = result["task_id"]
    print(f"Received Tripo AI refine task_id: {task_id}")

    # Poll for task completion
    model_url = await poll_tripo_task(task_id)

    assert model_url is not None
    print(f"Received refined model URL: {model_url}")

    # Download the generated model
    await download_file(model_url, f"refine_model_{task_id}.glb")


@pytest.mark.asyncio
async def test_generate_select_concept():
    """Test the /generate/select-concept endpoint (Tripo AI from concept)."""
    endpoint = f"{BASE_URL}/generate/select-concept"
    # To test select-concept, you need a URL of a generated 2D concept image.
    # This requires successfully running the image-to-image test first and getting a concept image URL.
    # Replace 'YOUR_CONCEPT_IMAGE_URL' with an actual URL of a generated concept image.
    concept_image_url = "YOUR_CONCEPT_IMAGE_URL" # Placeholder
    concept_task_id = "YOUR_CONCEPT_TASK_ID" # Placeholder (Optional, but included in schema)
    print("NOTE: Replace YOUR_CONCEPT_IMAGE_URL and YOUR_CONCEPT_TASK_ID with actual values for this test.")

    if concept_image_url == "YOUR_CONCEPT_IMAGE_URL":
         print("Skipping select concept test: YOUR_CONCEPT_IMAGE_URL is a placeholder.")
         pytest.skip("Requires a valid concept image URL.")

    request_data = {
        "concept_task_id": concept_task_id, # Use the dummy or real concept task ID
        "selected_image_url": concept_image_url
    }

    print(f"Calling {endpoint} with {request_data}...")
    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()

    assert "task_id" in result
    task_id = result["task_id"]
    print(f"Received Tripo AI task_id from concept: {task_id}")

    # Poll for task completion
    model_url = await poll_tripo_task(task_id)

    assert model_url is not None
    print(f"Received model URL from concept: {model_url}")

    # Download the generated model
    await download_file(model_url, f"select_concept_{task_id}.glb")


@pytest.mark.asyncio
async def test_get_task_status_tripo():
    """Test the /tasks/{task_id}/status endpoint for a Tripo AI task."""
    # To test this, you need a task_id from a previously initiated Tripo AI task.
    # Replace 'YOUR_TRIPO_TASK_ID' with an actual Tripo task ID.
    tripo_task_id = "YOUR_TRIPO_TASK_ID" # Placeholder
    print("NOTE: Replace YOUR_TRIPO_TASK_ID with an actual Tripo task ID for this test.")

    if tripo_task_id == "YOUR_TRIPO_TASK_ID":
        print("Skipping Tripo status test: YOUR_TRIPO_TASK_ID is a placeholder.")
        pytest.skip("Requires a valid Tripo task ID.")

    status_url = f"{BASE_URL}/tasks/{tripo_task_id}/status"

    print(f"Calling {status_url}?service=tripo...")
    async with httpx.AsyncClient() as client:
        response = await client.get(status_url, params={'service': 'tripo'})
        response.raise_for_status()
        status_data = response.json()

    print(f"Tripo task status: {status_data}")
    assert "status" in status_data
    assert status_data["status"] in ["pending", "processing", "completed", "failed", "unknown"]


@pytest.mark.asyncio
async def test_get_task_status_openai():
    """Test the /tasks/{task_id}/status endpoint for an OpenAI task."""
    # To test this, you need a task_id from a previously initiated OpenAI task.
    # Replace 'YOUR_OPENAI_TASK_ID' with an actual OpenAI task ID.
    # Note: As discussed, OpenAI image generation is typically synchronous,
    # so a real OpenAI task ID for polling might not be readily available
    # or the status endpoint might behave differently.
    openai_task_id = "YOUR_OPENAI_TASK_ID" # Placeholder
    print("NOTE: Replace YOUR_OPENAI_TASK_ID with an actual OpenAI task ID for this test.")

    if openai_task_id == "YOUR_OPENAI_TASK_ID":
         print("Skipping OpenAI status test: YOUR_OPENAI_TASK_ID is a placeholder.")
         pytest.skip("Requires a valid OpenAI task ID.")

    status_url = f"{BASE_URL}/tasks/{openai_task_id}/status"

    print(f"Calling {status_url}?service=openai...")
    async with httpx.AsyncClient() as client:
        response = await client.get(status_url, params={'service': 'openai'})
        response.raise_for_status()
        status_data = response.json()

    print(f"OpenAI task status: {status_data}")
    assert "status" in status_data
    # For MVP, we simulate completed status for OpenAI polling
    assert status_data["status"] == "completed"
    assert status_data.get("result_url") is None # Result URL is returned by generation endpoint directly 