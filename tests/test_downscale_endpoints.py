import pytest
import time
import uuid
import httpx
import asyncio
import os

# Import all shared helpers and utilities (same as other tests)
from .test_helpers import (
    BASE_URL, logger, download_file, print_test_summary, get_auth_headers
)

# --- Downscale Tests ---

@pytest.mark.asyncio
async def test_generate_downscale_basic(request):
    """Test basic downscale functionality."""
    start_time = time.time()
    client_task_id = f"test-downscale-basic-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/downscale"
    # Use correct Supabase project URL that matches the current environment
    input_image_url = "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    request_data = {
        "task_id": client_task_id,
        "input_image_asset_url": input_image_url,
        "max_size_mb": 0.5,
        "aspect_ratio_mode": "original",
        "output_format": "original"
    }

    logger.info(f"Calling {endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers=get_auth_headers())
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result
    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Wait for Celery task completion (Downscale is synchronous processing)
    polling_start = time.time()
    from app.celery_worker import celery_app
    celery_result = celery_app.AsyncResult(celery_task_id)
    
    # Wait for the task to complete
    max_wait_time = 120  # 2 minutes should be plenty for downscaling
    poll_interval = 2
    elapsed_time = 0
    
    while not celery_result.ready() and elapsed_time < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed_time += poll_interval
        print(f"⏳ Waiting for downscale processing... {elapsed_time}s elapsed")
    
    if not celery_result.ready():
        raise Exception(f"Downscale task timed out after {max_wait_time} seconds")
    
    if celery_result.failed():
        raise Exception(f"Downscale task failed: {celery_result.info}")
    
    task_result_data = celery_result.result
    processing_time = time.time() - polling_start
    
    print(f"🤖 Downscale Processing completed in {processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME: {processing_time:.2f}s")

    # Get the result URL
    asset_url = task_result_data.get('image_url')  # Downscale returns 'image_url'
    assert asset_url is not None, f"Image URL not found in response: {task_result_data}"
    logger.info(f"Received downscaled image URL: {asset_url}")

    # Download the downscaled image
    image_file_path, image_download_time = await download_file(asset_url, request.node.name, "downscaled.jpg")
    print(f"💾 Downscaled image downloaded in {image_download_time:.2f}s")
    
    assert os.path.exists(image_file_path)
    assert os.path.getsize(image_file_path) > 0

    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    logger.info(f"TOTAL TEST TIME: {total_test_time:.2f}s")

    # Test summary
    timings = {
        "API Response Time": api_response_time,
        "Downscale Processing": processing_time,
        "Image Download": image_download_time
    }
    locations = {
        "supabase_storage": {"input_image_url": input_image_url, "downscaled_asset_url": asset_url},
        "local_files": {"downscaled.jpg": image_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_downscale_square_mode(request):
    """Test downscale with square aspect ratio mode."""
    start_time = time.time()
    client_task_id = f"test-downscale-square-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/downscale"
    input_image_url = "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg"

    request_data = {
        "task_id": client_task_id,
        "input_image_asset_url": input_image_url,
        "max_size_mb": 0.3,
        "aspect_ratio_mode": "square",  # Test square padding
        "output_format": "png"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers=get_auth_headers())
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")

    # Wait for completion
    polling_start = time.time()
    from app.celery_worker import celery_app
    celery_result = celery_app.AsyncResult(celery_task_id)
    
    max_wait_time = 120
    poll_interval = 2
    elapsed_time = 0
    
    while not celery_result.ready() and elapsed_time < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed_time += poll_interval
        print(f"⏳ Waiting for square downscale... {elapsed_time}s elapsed")
    
    if celery_result.failed():
        raise Exception(f"Square downscale task failed: {celery_result.info}")
    
    task_result_data = celery_result.result
    processing_time = time.time() - polling_start
    
    print(f"🤖 Square Downscale Processing completed in {processing_time:.2f}s")

    asset_url = task_result_data.get('image_url')  # Downscale returns 'image_url'
    assert asset_url is not None

    # Download and verify
    image_file_path, image_download_time = await download_file(asset_url, request.node.name, "square_downscaled.png")
    print(f"💾 Square downscaled image downloaded in {image_download_time:.2f}s")
    
    assert os.path.exists(image_file_path)
    assert os.path.getsize(image_file_path) > 0

    # Test summary
    timings = {
        "API Response Time": api_response_time,
        "Square Downscale Processing": processing_time,
        "Image Download": image_download_time
    }
    locations = {
        "supabase_storage": {"input_image_url": input_image_url, "square_asset_url": asset_url},
        "local_files": {"square_downscaled.png": image_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_generate_downscale_format_conversion(request):
    """Test downscale with format conversion."""
    start_time = time.time()
    client_task_id = f"test-downscale-convert-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    
    endpoint = f"{BASE_URL}/generate/downscale"
    input_image_url = "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg"

    request_data = {
        "task_id": client_task_id,
        "input_image_asset_url": input_image_url,
        "max_size_mb": 0.2,
        "aspect_ratio_mode": "original",
        "output_format": "jpeg"  # Convert to JPEG
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers=get_auth_headers())
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")

    # Wait for completion
    polling_start = time.time()
    from app.celery_worker import celery_app
    celery_result = celery_app.AsyncResult(celery_task_id)
    
    max_wait_time = 120
    poll_interval = 2
    elapsed_time = 0
    
    while not celery_result.ready() and elapsed_time < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed_time += poll_interval
        print(f"⏳ Waiting for format conversion... {elapsed_time}s elapsed")
    
    if celery_result.failed():
        raise Exception(f"Format conversion task failed: {celery_result.info}")
    
    task_result_data = celery_result.result
    processing_time = time.time() - polling_start
    
    print(f"🤖 Format Conversion completed in {processing_time:.2f}s")

    asset_url = task_result_data.get('image_url')  # Downscale returns 'image_url'
    assert asset_url is not None

    # Download and verify
    image_file_path, image_download_time = await download_file(asset_url, request.node.name, "converted.jpeg")
    print(f"💾 Converted image downloaded in {image_download_time:.2f}s")
    
    assert os.path.exists(image_file_path)
    assert os.path.getsize(image_file_path) > 0

    # Test summary
    timings = {
        "API Response Time": api_response_time,
        "Format Conversion Processing": processing_time,
        "Image Download": image_download_time
    }
    locations = {
        "supabase_storage": {"input_image_url": input_image_url, "converted_asset_url": asset_url},
        "local_files": {"converted.jpeg": image_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations) 