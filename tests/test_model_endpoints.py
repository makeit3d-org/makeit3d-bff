import pytest
import time
import uuid
import httpx
import os
import asyncio

# Import all shared helpers and utilities
from .test_helpers import (
    BASE_URL, logger, download_file, poll_task_status, wait_for_celery_task, print_test_summary,
    supabase_handler, get_auth_headers
)

# --- Model Generation Tests ---

@pytest.mark.asyncio
async def test_generate_text_to_model(request):
    """Test 2.1: /generate/text-to-model endpoint (Tripo AI direct)."""
    start_time = time.time()
    client_task_id = f"test-t2m-{uuid.uuid4()}" # Client-generated task_id
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/text-to-model"
    prompt = "A violet colored cartoon flying elephant with big flapping ears"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    request_data = {
        "task_id": client_task_id,
        "provider": "tripo",
        "prompt": prompt,
        "texture_quality": "standard"
    }

    logger.info(f"Calling {endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers=get_auth_headers())
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result # This is the Celery task_id
    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Wait for Celery task completion (Tripo polling is handled internally by the Celery task)
    polling_start = time.time()
    
    # For Tripo, the Celery task handles the async polling internally and completes when done
    from app.celery_worker import celery_app
    celery_result = celery_app.AsyncResult(celery_task_id)
    
    # Wait for the task to complete with extended timeout for 3D model generation
    max_wait_time = 600  # 10 minutes for text-to-model
    poll_interval = 5    # Check every 5 seconds
    elapsed_time = 0
    
    while not celery_result.ready() and elapsed_time < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed_time += poll_interval
        print(f"⏳ Waiting for Tripo text-to-model... {elapsed_time}s elapsed")
    
    if not celery_result.ready():
        raise Exception(f"Tripo task timed out after {max_wait_time} seconds")
    
    if celery_result.failed():
        raise Exception(f"Tripo task failed: {celery_result.info}")
    
    task_result_data = celery_result.result
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Tripo AI Processing completed in {ai_processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME: {ai_processing_time:.2f}s")
    logger.info(f"Full task_result_data: {task_result_data}")

    model_url = task_result_data.get('result_url') # Celery task returns 'result_url'

    assert model_url is not None, f"Model result_url not found in response: {task_result_data}"
    logger.info(f"Received model Supabase URL: {model_url}")

    # Download the generated model
    model_file_path, model_download_time = await download_file(model_url, request.node.name, "model.glb")
    print(f"💾 Model downloaded in {model_download_time:.2f}s")
    logger.info(f"Model downloaded to: {model_file_path}")
    
    assert os.path.exists(model_file_path)
    assert os.path.getsize(model_file_path) > 0
    
    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    logger.info(f"TOTAL TEST TIME: {total_test_time:.2f}s")

    # Test summary
    timings = {
        "API Response Time": api_response_time,
        "Tripo AI Processing": ai_processing_time,
        "Model Download": model_download_time
    }
    locations = {
        "supabase_storage": {"model_asset_url": model_url},
        "local_files": {"model.glb": model_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_image_to_model(request):
    """Test 3.0: /generate/image-to-model endpoint (Tripo AI) using a client-provided Supabase image URL."""
    start_time = time.time()
    client_task_id = f"test-i2m-tripo-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    
    image_to_model_endpoint = f"{BASE_URL}/generate/image-to-model"

    # Simulate client uploading an image to their Supabase and providing the URL
    image_to_upload_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-front-concept.png" # Using a concept-like image

    logger.info(f"Running {request.node.name} for task_id: {client_task_id} with input image URL: {image_to_upload_url}")

    # 1. Download the public image
    input_download_start = time.time()
    async with httpx.AsyncClient() as client:
        img_response = await client.get(image_to_upload_url)
        img_response.raise_for_status()
        image_content = img_response.content
        original_filename = image_to_upload_url.split("/")[-1]
    input_download_time = time.time() - input_download_start
    
    print(f"📥 INPUT IMAGE DOWNLOADED: {original_filename} in {input_download_time:.2f}s")
    logger.info(f"INPUT IMAGE DOWNLOADED: {original_filename}")

    # 2. Upload image to Supabase (simulating client's asset)
    upload_start = time.time()
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/image-to-model",
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/png" if original_filename.endswith('.png') else "image/jpeg"
    )
    upload_time = time.time() - upload_start
    print(f"📤 Image uploaded to Supabase in {upload_time:.2f}s")
    logger.info(f"Input image uploaded to Supabase, URL: {input_supabase_url}")

    request_data = {
        "task_id": client_task_id,
        "provider": "tripo",
        "input_image_asset_urls": [input_supabase_url], 
        "prompt": "3D model from image",
        "texture_quality": "standard" # Match Pydantic ImageToModelRequest
    }

    logger.info(f"Calling {image_to_model_endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(image_to_model_endpoint, json=request_data, headers=get_auth_headers())
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result
    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Wait for Celery task completion (Tripo polling is handled internally by the Celery task)
    polling_start = time.time()
    
    from app.celery_worker import celery_app
    celery_result = celery_app.AsyncResult(celery_task_id)
    
    # Wait for the task to complete with extended timeout for 3D model generation
    max_wait_time = 600  # 10 minutes for image-to-model
    poll_interval = 5    # Check every 5 seconds
    elapsed_time = 0
    
    while not celery_result.ready() and elapsed_time < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed_time += poll_interval
        print(f"⏳ Waiting for Tripo image-to-model... {elapsed_time}s elapsed")
    
    if not celery_result.ready():
        raise Exception(f"Tripo task timed out after {max_wait_time} seconds")
    
    if celery_result.failed():
        raise Exception(f"Tripo task failed: {celery_result.info}")
    
    task_result_data = celery_result.result
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Tripo AI Processing completed in {ai_processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME: {ai_processing_time:.2f}s")

    model_url = task_result_data.get('result_url') or task_result_data.get('asset_url')  # Support both field names

    assert model_url is not None, f"Model URL not found in response: {task_result_data}"
    logger.info(f"Received model Supabase URL: {model_url}")

    # Download the generated model
    model_file_path, model_download_time = await download_file(model_url, request.node.name, "model.glb")
    print(f"💾 Model downloaded in {model_download_time:.2f}s")
    logger.info(f"Model downloaded to: {model_file_path}")
    
    assert os.path.exists(model_file_path)
    assert os.path.getsize(model_file_path) > 0

    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    logger.info(f"TOTAL TEST TIME: {total_test_time:.2f}s")

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "Tripo AI Processing": ai_processing_time,
        "Model Download": model_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": input_supabase_url, "model_asset_url": model_url},
        "local_files": {"model.glb": model_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_image_to_model_stability(request):
    """Test 3.1: /generate/image-to-model endpoint (Stability AI SPAR3D)."""
    start_time = time.time()
    client_task_id = f"test-i2m-stability-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    
    image_to_model_endpoint = f"{BASE_URL}/generate/image-to-model"
    image_to_upload_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-front-concept.png"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id} with input image URL: {image_to_upload_url}")

    # Download and upload input image
    input_download_start = time.time()
    async with httpx.AsyncClient() as client:
        img_response = await client.get(image_to_upload_url)
        img_response.raise_for_status()
        image_content = img_response.content
        original_filename = image_to_upload_url.split("/")[-1]
    input_download_time = time.time() - input_download_start
    
    upload_start = time.time()
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/image-to-model",
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/png" if original_filename.endswith('.png') else "image/jpeg"
    )
    upload_time = time.time() - upload_start
    print(f"📤 Image uploaded to Supabase in {upload_time:.2f}s")

    request_data = {
        "task_id": client_task_id,
        "provider": "stability",
        "input_image_asset_urls": [input_supabase_url],
        "prompt": "High quality 3D model",
        "texture_resolution": 1024,
        "remesh": "quad",
        "foreground_ratio": 1.0  # Must be >= 1.0 according to Stability API
    }

    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(image_to_model_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")

    # Wait for Celery task completion (Stability is synchronous)
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(celery_task_id, "Stability", total_timeout=300.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Stability AI Processing completed in {ai_processing_time:.2f}s")

    model_url = task_result_data.get('result_url') or task_result_data.get('asset_url')  # Support both field names
    assert model_url is not None, f"Model URL not found in response: {task_result_data}"

    # Download the generated model
    model_file_path, model_download_time = await download_file(model_url, request.node.name, "stability_model.glb")
    print(f"💾 Model downloaded in {model_download_time:.2f}s")
    
    assert os.path.exists(model_file_path)
    assert os.path.getsize(model_file_path) > 0

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "Stability AI Processing": ai_processing_time,
        "Model Download": model_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": input_supabase_url, "model_asset_url": model_url},
        "local_files": {"stability_model.glb": model_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_multiview_to_model(request):
    """Test 3.1: /generate/image-to-model endpoint with multiple images (multiview mode)."""
    start_time = time.time()
    client_task_id = f"test-multiview-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    
    image_to_model_endpoint = f"{BASE_URL}/generate/image-to-model"
    
    # Multiview images in the required order: [front, left, back, right]
    multiview_image_urls = [
        "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-front-concept.png",  # front
        "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-left-concept.png",   # left
        "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-back--concept.png",  # back
        "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-right-concept.png"   # right
    ]
    view_names = ["front", "left", "back", "right"]
    
    logger.info(f"Running {request.node.name} for task_id: {client_task_id} with {len(multiview_image_urls)} multiview images")

    # Download and upload all images
    input_supabase_urls = []
    total_input_download_time = 0
    total_upload_time = 0
    
    for i, image_url in enumerate(multiview_image_urls):
        download_start = time.time()
        async with httpx.AsyncClient() as client:
            img_response = await client.get(image_url)
            img_response.raise_for_status()
            image_content = img_response.content
            original_filename = f"{view_names[i]}_{image_url.split('/')[-1]}"
        single_download_time = time.time() - download_start
        total_input_download_time += single_download_time
        
        print(f"📥 {view_names[i].upper()} view downloaded: {original_filename} in {single_download_time:.2f}s")
        logger.info(f"INPUT IMAGE DOWNLOADED: {original_filename} for {view_names[i]} view")

        # Upload to Supabase with view name in path - TEST FOLDER
        upload_start = time.time()
        input_supabase_url = await supabase_handler.upload_asset_to_storage(
            task_id=client_task_id,
            asset_type_plural="test_inputs/multiview-to-model",
            file_name=original_filename,
            asset_data=image_content,
            content_type="image/png" if original_filename.endswith('.png') else "image/jpeg"
        )
        single_upload_time = time.time() - upload_start
        total_upload_time += single_upload_time
        
        input_supabase_urls.append(input_supabase_url)
        print(f"📤 {view_names[i].upper()} view uploaded in {single_upload_time:.2f}s")
        logger.info(f"✓ {view_names[i]} view uploaded to Supabase: {input_supabase_url}")

    print(f"📥 All input downloads completed in {total_input_download_time:.2f}s")
    print(f"📤 All uploads completed in {total_upload_time:.2f}s")
    logger.info(f"All {len(input_supabase_urls)} images uploaded. Calling multiview endpoint...")

    request_data = {
        "task_id": client_task_id,
        "provider": "tripo",
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
        api_response_time = time.time() - api_call_start
        
    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"API RESPONSE TIME: {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result
    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Wait for Celery task completion (Tripo polling is handled internally by the Celery task)
    polling_start = time.time()
    
    from app.celery_worker import celery_app
    celery_result = celery_app.AsyncResult(celery_task_id)
    
    # Wait for the task to complete with extended timeout for multiview processing
    max_wait_time = 900  # 15 minutes for multiview (longer than single image)
    poll_interval = 5    # Check every 5 seconds
    elapsed_time = 0
    
    while not celery_result.ready() and elapsed_time < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed_time += poll_interval
        print(f"⏳ Waiting for Tripo multiview processing... {elapsed_time}s elapsed")
    
    if not celery_result.ready():
        raise Exception(f"Tripo multiview task timed out after {max_wait_time} seconds")
    
    if celery_result.failed():
        raise Exception(f"Tripo multiview task failed: {celery_result.info}")
    
    task_result_data = celery_result.result
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Tripo AI Multiview Processing completed in {ai_processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME (multiview): {ai_processing_time:.2f}s")

    model_url = task_result_data.get('result_url') or task_result_data.get('asset_url')  # Support both field names

    assert model_url is not None, f"Model URL not found in response: {task_result_data}"
    logger.info(f"Received multiview model Supabase URL: {model_url}")

    # Download the generated multiview model
    model_file_path, model_download_time = await download_file(model_url, request.node.name, "multiview_model.glb")
    print(f"💾 Multiview model downloaded in {model_download_time:.2f}s")
    logger.info(f"Multiview model downloaded to: {model_file_path}")
    
    assert os.path.exists(model_file_path)
    assert os.path.getsize(model_file_path) > 0

    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    logger.info(f"TOTAL TEST TIME: {total_test_time:.2f}s")

    # Test summary
    timings = {
        "Total Input Downloads": total_input_download_time,
        "Total Input Uploads": total_upload_time,
        "API Response Time": api_response_time,
        "Tripo AI Multiview Processing": ai_processing_time,
        "Model Download": model_download_time
    }
    locations = {
        "supabase_storage": {
            "multiview_inputs": input_supabase_urls,
            "model_asset_url": model_url
        },
        "local_files": {"multiview_model.glb": model_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations) 