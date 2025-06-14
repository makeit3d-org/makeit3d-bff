import pytest
import time
import uuid
import httpx
import os

# Import all shared helpers and utilities
from .test_helpers import (
    BASE_URL, logger, download_file, poll_task_status, wait_for_celery_task, print_test_summary,
    supabase_handler
)

# --- Image Generation Tests ---

@pytest.mark.asyncio
async def test_generate_image_to_image(request):
    """Test 1.1: /generate/image-to-image endpoint (OpenAI)."""
    start_time = time.time()
    client_task_id = f"test-i2i-openai-{uuid.uuid4()}" # Client-generated task_id
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/image-to-image"
    image_to_upload_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"
    prompt = "Transform me into a toy action figure. Make it look like I am made out of plastic. Make sure to still make it look like me as much as possible. Include my whole body with no background, surroundings or detached objects."
    style = "Cartoonish, cute but still realistic."
    background = "transparent"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    # 1. Download the public image
    input_download_start = time.time()
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_to_upload_url)
        image_response.raise_for_status()
        image_content = image_response.content
        original_filename = image_to_upload_url.split("/")[-1]
    input_download_time = time.time() - input_download_start
    
    print(f"📥 INPUT IMAGE DOWNLOADED: {original_filename} in {input_download_time:.2f}s")
    logger.info(f"INPUT IMAGE DOWNLOADED: {original_filename}")

    # 2. Upload the image to Supabase Storage (simulating client upload) - TEST FOLDER
    upload_start = time.time()
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/image-to-image", 
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/jpeg"
    )
    upload_time = time.time() - upload_start
    print(f"📤 Image uploaded to Supabase in {upload_time:.2f}s")
    logger.info(f"Image uploaded to Supabase URL: {input_supabase_url}")
    
    # 3. Call BFF endpoint with Supabase URL
    request_data = {
        "task_id": client_task_id,
        "provider": "openai",
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
        api_response_time = time.time() - api_call_start

    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result # Celery task_id
    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Poll for task completion and get the result data
    logger.info(f"Polling for completion of OpenAI task {celery_task_id}...")
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "openai", poll_interval=2, total_timeout=180.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 OpenAI Processing completed in {ai_processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME (includes OpenAI generation + Supabase storage): {ai_processing_time:.2f}s")

    # Verify that the response contains the expected asset URL
    assert task_result_data.get('status') == 'complete'
    assert 'asset_url' in task_result_data
    asset_url = task_result_data['asset_url'] # This is the Supabase URL
    
    # For image-to-image, we expect at least one generated concept
    assert asset_url is not None
    logger.info(f"Received concept image Supabase URL: {asset_url}")

    # Download the generated concept image
    concept_file_path, concept_download_time = await download_file(asset_url, request.node.name, "concept_image.png")
    print(f"💾 Concept image downloaded in {concept_download_time:.2f}s")

    expected_n = request_data.get('n', 1)
    assert isinstance(asset_url, str)
    assert len(asset_url) > 0

    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    logger.info(f"TOTAL TEST TIME: {total_test_time:.2f}s")

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "OpenAI AI Processing": ai_processing_time,
        "Concept Download": concept_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": input_supabase_url, "concept_asset_url": asset_url},
        "local_files": {"concept_image.png": concept_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_image_to_image_stability(request):
    """Test 1.2: /generate/image-to-image endpoint (Stability AI)."""
    start_time = time.time()
    client_task_id = f"test-i2i-stability-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/image-to-image"
    image_to_upload_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"
    prompt = "Transform into a cartoon character with vibrant colors"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    # Download and upload input image
    input_download_start = time.time()
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_to_upload_url)
        image_response.raise_for_status()
        image_content = image_response.content
        original_filename = image_to_upload_url.split("/")[-1]
    input_download_time = time.time() - input_download_start
    
    upload_start = time.time()
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/image-to-image", 
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/jpeg"
    )
    upload_time = time.time() - upload_start
    
    # Call Stability AI endpoint
    request_data = {
        "task_id": client_task_id,
        "provider": "stability",
        "input_image_asset_url": input_supabase_url,
        "prompt": prompt,
        "style_preset": "anime",
        "fidelity": 0.8,
        "output_format": "png"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")

    # Wait for Celery task completion (Stability is synchronous)
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(celery_task_id, "Stability", total_timeout=180.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Stability AI Processing completed in {ai_processing_time:.2f}s")

    asset_url = task_result_data['asset_url']
    concept_file_path, concept_download_time = await download_file(asset_url, request.node.name, "stability_concept.png")

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "Stability AI Processing": ai_processing_time,
        "Concept Download": concept_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": input_supabase_url, "concept_asset_url": asset_url},
        "local_files": {"stability_concept.png": concept_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_image_to_image_recraft(request):
    """Test 1.3: /generate/image-to-image endpoint (Recraft AI)."""
    start_time = time.time()
    client_task_id = f"test-i2i-recraft-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/image-to-image"
    image_to_upload_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"
    prompt = "Transform into a digital art style with bold colors"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    # Download and upload input image
    input_download_start = time.time()
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_to_upload_url)
        image_response.raise_for_status()
        image_content = image_response.content
        original_filename = image_to_upload_url.split("/")[-1]
    input_download_time = time.time() - input_download_start
    
    upload_start = time.time()
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/image-to-image", 
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/jpeg"
    )
    upload_time = time.time() - upload_start
    
    # Call Recraft AI endpoint
    request_data = {
        "task_id": client_task_id,
        "provider": "recraft",
        "input_image_asset_url": input_supabase_url,
        "prompt": prompt,
        "style": "digital_illustration",
        "strength": 0.8,
        "n": 1
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")

    # Wait for Celery task completion (Recraft is synchronous)
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(celery_task_id, "Recraft", total_timeout=180.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Recraft AI Processing completed in {ai_processing_time:.2f}s")

    asset_url = task_result_data['asset_url']
    concept_file_path, concept_download_time = await download_file(asset_url, request.node.name, "recraft_concept.png")

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "Recraft AI Processing": ai_processing_time,
        "Concept Download": concept_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": input_supabase_url, "concept_asset_url": asset_url},
        "local_files": {"recraft_concept.png": concept_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_text_to_image(request):
    """Test 1.5: /generate/text-to-image endpoint (OpenAI)."""
    start_time = time.time()
    client_task_id = f"test-t2i-openai-{uuid.uuid4()}" # Client-generated task_id
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/text-to-image"
    prompt = "A violet colored cartoon flying elephant with big flapping ears"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    # Test with OpenAI provider
    request_data = {
        "task_id": client_task_id,
        "provider": "openai",
        "prompt": prompt,
        "style": "vivid",
        "n": 1,
        "size": "1024x1024",
        "quality": "standard"
    }

    logger.info(f"Calling {endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result # This is the Celery task_id
    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Poll for task completion and get result URL
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "openai", total_timeout=120.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 OpenAI Processing completed in {ai_processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME: {ai_processing_time:.2f}s")
    logger.info(f"Full task_result_data: {task_result_data}")

    image_url = task_result_data.get('asset_url') # Expecting 'asset_url' based on TaskStatusResponse schema

    assert image_url is not None, f"Image asset_url not found in response: {task_result_data}"
    logger.info(f"Received image Supabase URL: {image_url}")

    # Download the generated image
    image_file_path, image_download_time = await download_file(image_url, request.node.name, "image.png")
    print(f"💾 Image downloaded in {image_download_time:.2f}s")
    logger.info(f"Image downloaded to: {image_file_path}")
    
    assert os.path.exists(image_file_path)
    assert os.path.getsize(image_file_path) > 0
    
    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    logger.info(f"TOTAL TEST TIME: {total_test_time:.2f}s")

    # Test summary
    timings = {
        "API Response Time": api_response_time,
        "OpenAI Processing": ai_processing_time,
        "Image Download": image_download_time
    }
    locations = {
        "supabase_storage": {"image_asset_url": image_url},
        "local_files": {"image.png": image_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_text_to_image_stability(request):
    """Test 1.6: /generate/text-to-image endpoint (Stability AI)."""
    start_time = time.time()
    client_task_id = f"test-t2i-stability-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/text-to-image"
    prompt = "A majestic dragon flying over a fantasy castle at sunset"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    request_data = {
        "task_id": client_task_id,
        "provider": "stability",
        "prompt": prompt,
        "style_preset": "fantasy-art",
        "aspect_ratio": "16:9",
        "output_format": "png"
    }

    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")

    # Wait for Celery task completion (Stability is synchronous)
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(celery_task_id, "Stability", total_timeout=120.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Stability AI Processing completed in {ai_processing_time:.2f}s")

    image_url = task_result_data.get('asset_url')
    assert image_url is not None, f"Image asset_url not found in response: {task_result_data}"

    # Download the generated image
    image_file_path, image_download_time = await download_file(image_url, request.node.name, "stability_image.png")
    print(f"💾 Image downloaded in {image_download_time:.2f}s")
    
    assert os.path.exists(image_file_path)
    assert os.path.getsize(image_file_path) > 0

    # Test summary
    timings = {
        "API Response Time": api_response_time,
        "Stability AI Processing": ai_processing_time,
        "Image Download": image_download_time
    }
    locations = {
        "supabase_storage": {"image_asset_url": image_url},
        "local_files": {"stability_image.png": image_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_text_to_image_recraft(request):
    """Test 1.7: /generate/text-to-image endpoint (Recraft AI)."""
    start_time = time.time()
    client_task_id = f"test-t2i-recraft-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/text-to-image"
    prompt = "A futuristic robot in a cyberpunk city with neon lights"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    request_data = {
        "task_id": client_task_id,
        "provider": "recraft",
        "prompt": prompt,
        "style": "digital_illustration",
        "substyle": "cyberpunk",
        "n": 1,
        "size": "1024x1024"
    }

    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")

    # Wait for Celery task completion (Recraft is synchronous)
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(celery_task_id, "Recraft", total_timeout=120.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Recraft AI Processing completed in {ai_processing_time:.2f}s")

    image_url = task_result_data.get('asset_url')
    assert image_url is not None, f"Image asset_url not found in response: {task_result_data}"

    # Download the generated image
    image_file_path, image_download_time = await download_file(image_url, request.node.name, "recraft_image.png")
    print(f"💾 Image downloaded in {image_download_time:.2f}s")
    
    assert os.path.exists(image_file_path)
    assert os.path.getsize(image_file_path) > 0

    # Test summary
    timings = {
        "API Response Time": api_response_time,
        "Recraft AI Processing": ai_processing_time,
        "Image Download": image_download_time
    }
    locations = {
        "supabase_storage": {"image_asset_url": image_url},
        "local_files": {"recraft_image.png": image_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_remove_background_stability(request):
    """Test 5.1: /generate/remove-background endpoint (Stability AI)."""
    start_time = time.time()
    client_task_id = f"test-rmbg-stability-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/remove-background"
    image_to_upload_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    # Download and upload input image
    input_download_start = time.time()
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_to_upload_url)
        image_response.raise_for_status()
        image_content = image_response.content
        original_filename = image_to_upload_url.split("/")[-1]
    input_download_time = time.time() - input_download_start
    
    upload_start = time.time()
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/remove-background", 
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/jpeg"
    )
    upload_time = time.time() - upload_start
    
    # Call Stability AI endpoint
    request_data = {
        "task_id": client_task_id,
        "provider": "stability",
        "input_image_asset_url": input_supabase_url,
        "output_format": "png"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")

    # Wait for Celery task completion (Stability is synchronous)
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(celery_task_id, "Stability", total_timeout=120.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Stability AI Processing completed in {ai_processing_time:.2f}s")

    asset_url = task_result_data['asset_url']
    result_file_path, result_download_time = await download_file(asset_url, request.node.name, "stability_no_bg.png")

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "Stability AI Processing": ai_processing_time,
        "Result Download": result_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": input_supabase_url, "result_asset_url": asset_url},
        "local_files": {"stability_no_bg.png": result_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_remove_background_recraft(request):
    """Test 5.2: /generate/remove-background endpoint (Recraft AI)."""
    start_time = time.time()
    client_task_id = f"test-rmbg-recraft-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/remove-background"
    image_to_upload_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    # Download and upload input image
    input_download_start = time.time()
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_to_upload_url)
        image_response.raise_for_status()
        image_content = image_response.content
        original_filename = image_to_upload_url.split("/")[-1]
    input_download_time = time.time() - input_download_start
    
    upload_start = time.time()
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/remove-background", 
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/jpeg"
    )
    upload_time = time.time() - upload_start
    
    # Call Recraft AI endpoint
    request_data = {
        "task_id": client_task_id,
        "provider": "recraft",
        "input_image_asset_url": input_supabase_url,
        "response_format": "png"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")

    # Wait for Celery task completion (Recraft is synchronous)
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(celery_task_id, "Recraft", total_timeout=120.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Recraft AI Processing completed in {ai_processing_time:.2f}s")

    asset_url = task_result_data['asset_url']
    result_file_path, result_download_time = await download_file(asset_url, request.node.name, "recraft_no_bg.png")

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "Recraft AI Processing": ai_processing_time,
        "Result Download": result_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": input_supabase_url, "result_asset_url": asset_url},
        "local_files": {"recraft_no_bg.png": result_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_sketch_to_image(request):
    """Test 4.1: /generate/sketch-to-image endpoint (Stability AI)."""
    start_time = time.time()
    client_task_id = f"test-s2i-stability-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/sketch-to-image"
    
    # Use a public sketch image for testing
    public_sketch_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public/sketch-cat.jpg"
    logger.info(f"Running {request.node.name} for task_id: {client_task_id}. Using public sketch: {public_sketch_url}")

    # Download and upload input sketch
    input_download_start = time.time()
    async with httpx.AsyncClient() as client:
        sketch_response = await client.get(public_sketch_url)
        sketch_response.raise_for_status()
        sketch_content = sketch_response.content
        original_sketch_filename = public_sketch_url.split("/")[-1]
    input_download_time = time.time() - input_download_start
    
    print(f"📥 INPUT SKETCH DOWNLOADED: {original_sketch_filename} in {input_download_time:.2f}s")
    logger.info(f"INPUT SKETCH DOWNLOADED: {original_sketch_filename}")

    upload_start = time.time()
    input_sketch_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/sketch-to-image",
        file_name=original_sketch_filename,
        asset_data=sketch_content,
        content_type="image/jpeg" if original_sketch_filename.endswith('.jpg') else "image/png"
    )
    upload_time = time.time() - upload_start
    print(f"📤 Sketch uploaded to Supabase in {upload_time:.2f}s")
    logger.info(f"Input sketch uploaded to Supabase, URL: {input_sketch_supabase_url}")

    # Call Stability AI sketch-to-image endpoint
    request_data = {
        "task_id": client_task_id,
        "provider": "stability",
        "input_sketch_asset_url": input_sketch_supabase_url,
        "prompt": "Transform this sketch into a realistic colorful image",
        "control_strength": 0.8,
        "style_preset": "photographic",
        "output_format": "png"
    }

    logger.info(f"Calling {endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result
    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Wait for Celery task completion (Stability is synchronous)
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(celery_task_id, "Stability", total_timeout=180.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Stability AI Processing completed in {ai_processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME: {ai_processing_time:.2f}s")

    asset_url = task_result_data.get('asset_url')

    assert asset_url is not None, f"Asset asset_url not found in response: {task_result_data}"
    logger.info(f"Received image Supabase URL: {asset_url}")

    # Download the generated image
    image_file_path, image_download_time = await download_file(asset_url, request.node.name, "sketch_to_image.png")
    print(f"💾 Image downloaded in {image_download_time:.2f}s")
    logger.info(f"Image downloaded to: {image_file_path}")
    
    assert os.path.exists(image_file_path)
    assert os.path.getsize(image_file_path) > 0

    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    logger.info(f"TOTAL TEST TIME: {total_test_time:.2f}s")

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "Stability AI Processing": ai_processing_time,
        "Image Download": image_download_time
    }
    locations = {
        "supabase_storage": {"input_sketch_asset_url": input_sketch_supabase_url, "image_asset_url": asset_url},
        "local_files": {"sketch_to_image.png": image_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_image_inpaint(request):
    """Test 5.1: /generate/image-inpaint endpoint (Recraft AI)."""
    start_time = time.time()
    client_task_id = f"test-inpaint-recraft-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/image-inpaint"
    
    # Use public image and mask for testing
    public_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept"
    public_mask_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept-mask.png"
    
    timings = {}
    locations = {}
    
    # 1. Download and upload input image to test storage
    step_start_time = time.time()
    print("📥 Downloading and uploading input image...")
    try:
        input_image_bytes = await download_file(public_image_url, "input_image", "png")
        input_image_supabase_url = await supabase_handler.upload_asset_to_storage(
            task_id=client_task_id,
            asset_type_plural="test_inputs",
            file_name="input_image.png",
            asset_data=input_image_bytes,
            content_type="image/png"
        )
        timings["Upload Input Image"] = f"{time.time() - step_start_time:.2f}s"
        locations["Input Image"] = input_image_supabase_url
        print(f"✅ Input image uploaded to: {input_image_supabase_url}")
    except Exception as e:
        timings["Upload Input Image"] = f"Failed: {e}"
        print(f"❌ Failed to upload input image: {e}")
        raise
    
    # 2. Download and upload mask image to test storage
    step_start_time = time.time()
    print("📥 Downloading and uploading mask image...")
    try:
        mask_image_bytes = await download_file(public_mask_url, "mask_image", "png")
        mask_image_supabase_url = await supabase_handler.upload_asset_to_storage(
            task_id=client_task_id,
            asset_type_plural="test_inputs",
            file_name="mask_image.png",
            asset_data=mask_image_bytes,
            content_type="image/png"
        )
        timings["Upload Mask Image"] = f"{time.time() - step_start_time:.2f}s"
        locations["Mask Image"] = mask_image_supabase_url
        print(f"✅ Mask image uploaded to: {mask_image_supabase_url}")
    except Exception as e:
        timings["Upload Mask Image"] = f"Failed: {e}"
        print(f"❌ Failed to upload mask image: {e}")
        raise
    
    # 3. Call BFF endpoint
    step_start_time = time.time()
    print("🔄 Calling BFF /generate/image-inpaint endpoint...")
    
    payload = {
        "task_id": client_task_id,
        "provider": "recraft",
        "input_image_asset_url": input_image_supabase_url,
        "input_mask_asset_url": mask_image_supabase_url,
        "prompt": "add large colorful feathery wings with rainbow colors",
        "negative_prompt": "blurry, low quality, distorted, deformed",
        "n": 1,
        "style": "realistic_image",
        "model": "recraftv3",
        "response_format": "url"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            response_data = response.json()
            
        celery_task_id = response_data.get("celery_task_id")
        if not celery_task_id:
            raise Exception("No celery_task_id in response")
            
        timings["BFF API Call"] = f"{time.time() - step_start_time:.2f}s"
        print(f"✅ BFF responded with Celery task ID: {celery_task_id}")
        
    except Exception as e:
        timings["BFF API Call"] = f"Failed: {e}"
        print(f"❌ BFF API call failed: {e}")
        raise
    
    # 4. Poll for completion
    step_start_time = time.time()
    print("⏳ Polling for task completion...")
    
    try:
        final_status = await poll_task_status(celery_task_id, "openai", poll_interval=3, total_timeout=120.0)
        timings["Task Polling"] = f"{time.time() - step_start_time:.2f}s"
        
        if final_status["status"] != "complete":
            raise Exception(f"Task failed with status: {final_status}")
            
        asset_url = final_status.get("asset_url")
        if not asset_url:
            raise Exception("No asset_url in final status")
            
        locations["Generated Image"] = asset_url
        print(f"✅ Task completed! Generated image URL: {asset_url}")
        
    except Exception as e:
        timings["Task Polling"] = f"Failed: {e}"
        print(f"❌ Task polling failed: {e}")
        raise
    
    # 5. Download and verify the generated image
    step_start_time = time.time()
    print("📥 Downloading generated image...")
    
    try:
        generated_image_bytes = await download_file(asset_url, "generated_inpaint", "png")
        
        if len(generated_image_bytes) < 1000:  # Basic size check
            raise Exception(f"Generated image seems too small: {len(generated_image_bytes)} bytes")
            
        timings["Download Generated Image"] = f"{time.time() - step_start_time:.2f}s"
        print(f"✅ Downloaded generated image: {len(generated_image_bytes)} bytes")
        
    except Exception as e:
        timings["Download Generated Image"] = f"Failed: {e}"
        print(f"❌ Failed to download generated image: {e}")
        raise
    
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_search_and_recolor(request):
    """Test 7.1: /generate/search-and-recolor endpoint (Stability AI)."""
    start_time = time.time()
    client_task_id = f"test-search-recolor-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/search-and-recolor"
    # Using the cat concept image to change the colors
    image_to_upload_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept"
    prompt = "light blue cat with dark blue stripes, maintaining the same pose and expression"
    select_prompt = "cat"  # What to search for and recolor in the image

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    # Download and upload input image
    input_download_start = time.time()
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_to_upload_url)
        image_response.raise_for_status()
        image_content = image_response.content
        original_filename = image_to_upload_url.split("/")[-1]
    input_download_time = time.time() - input_download_start
    
    print(f"📥 INPUT IMAGE DOWNLOADED: {original_filename} in {input_download_time:.2f}s")
    logger.info(f"INPUT IMAGE DOWNLOADED: {original_filename}")
    
    upload_start = time.time()
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/search-and-recolor", 
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/png" if original_filename.endswith('.png') else "image/jpeg"
    )
    upload_time = time.time() - upload_start
    print(f"📤 Image uploaded to Supabase in {upload_time:.2f}s")
    logger.info(f"Image uploaded to Supabase URL: {input_supabase_url}")
    
    # Call Stability AI search-and-recolor endpoint
    request_data = {
        "task_id": client_task_id,
        "provider": "stability",
        "input_image_asset_url": input_supabase_url,
        "prompt": prompt,
        "select_prompt": select_prompt,
        "negative_prompt": "blurry, low quality, distorted, orange, tan, brown, yellow",
        "grow_mask": 3,
        "seed": 0,
        "output_format": "png",
        "style_preset": None
    }

    logger.info(f"Calling {endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result
    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Wait for Celery task completion (Stability is synchronous)
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(celery_task_id, "Stability", total_timeout=180.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Stability AI Processing completed in {ai_processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME: {ai_processing_time:.2f}s")

    assert task_result_data.get('status') == 'complete'
    assert 'asset_url' in task_result_data
    asset_url = task_result_data['asset_url']
    
    assert asset_url is not None
    logger.info(f"Received recolored image Supabase URL: {asset_url}")

    # Download the recolored image
    recolored_file_path, recolored_download_time = await download_file(asset_url, request.node.name, "recolored_image.png")
    print(f"💾 Recolored image downloaded in {recolored_download_time:.2f}s")
    logger.info(f"Recolored image downloaded to: {recolored_file_path}")
    
    assert os.path.exists(recolored_file_path)
    assert os.path.getsize(recolored_file_path) > 0

    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    logger.info(f"TOTAL TEST TIME: {total_test_time:.2f}s")

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "Stability AI Processing": ai_processing_time,
        "Recolored Download": recolored_download_time
    }
    locations = {
        "supabase_storage": {
            "input_image_asset_url": input_supabase_url, 
            "recolored_asset_url": asset_url
        },
        "local_files": {"recolored_image.png": recolored_file_path},
        "api_endpoints": {
            "/generate/search-and-recolor": {
                "provider": "stability",
                "prompt": prompt,
                "select_prompt": select_prompt,
                "operation": "search_and_recolor"
            }
        }
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_image_to_image_flux(request):
    """Test 1.4: /generate/image-to-image endpoint (Flux/BFL)."""
    start_time = time.time()
    client_task_id = f"test-i2i-flux-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/image-to-image"
    image_to_upload_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"
    prompt = "Change the background to a futuristic cityscape at dusk."

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    # Download and upload input image
    input_download_start = time.time()
    async with httpx.AsyncClient() as client:
        image_response = await client.get(image_to_upload_url)
        image_response.raise_for_status()
        image_content = image_response.content
        original_filename = image_to_upload_url.split("/")[-1]
    input_download_time = time.time() - input_download_start
    
    upload_start = time.time()
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/image-to-image", 
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/jpeg"
    )
    upload_time = time.time() - upload_start
    
    # Call Flux endpoint
    request_data = {
        "task_id": client_task_id,
        "provider": "flux",
        "input_image_asset_url": input_supabase_url,
        "prompt": prompt,
        # Add any Flux-specific params if needed
        "aspect_ratio": "1:1",
        "output_format": "png",
        "safety_tolerance": 2
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")

    # Wait for Celery task completion (Flux is asynchronous but handled in Celery)
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(celery_task_id, "Flux", poll_interval=2, total_timeout=180.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Flux AI Processing completed in {ai_processing_time:.2f}s")

    asset_url = task_result_data['asset_url']
    concept_file_path, concept_download_time = await download_file(asset_url, request.node.name, "flux_concept.png")

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "Flux AI Processing": ai_processing_time,
        "Concept Download": concept_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": input_supabase_url, "concept_asset_url": asset_url},
        "local_files": {"flux_concept.png": concept_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations) 