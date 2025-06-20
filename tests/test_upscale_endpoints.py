import pytest
import time
import uuid
import httpx
import os

# Import all shared helpers and utilities
from .test_helpers import (
    BASE_URL, logger, download_file, wait_for_celery_task, print_test_summary,
    supabase_handler, get_auth_headers
)

# --- Image Upscaling Tests ---

@pytest.mark.asyncio
async def test_generate_upscale_stability(request):
    """Test: /generate/upscale endpoint with Stability AI."""
    start_time = time.time()
    client_task_id = f"test-upscale-stability-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/upscale"
    image_to_upload_url = "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    # 3. Call BFF endpoint
    request_data = {
        "task_id": client_task_id,
        "provider": "stability",
        "input_image_asset_url": image_to_upload_url,
        "model": "fast",
        "prompt": "a high-resolution photo of a boy",
        "output_format": "png"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers=get_auth_headers())
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start
    print(f"🌐 API Response received in {api_response_time:.2f}s")

    task_id = result["task_id"]
    print(f"🆔 Task ID: {task_id}")

    # 4. Wait for Celery task completion
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(task_id, "Stability", total_timeout=180.0)
    ai_processing_time = time.time() - polling_start
    print(f"🤖 Stability AI Processing completed in {ai_processing_time:.2f}s")

    # 5. Download and verify the result
    asset_url = task_result_data['asset_url']
    upscaled_file_path, upscaled_download_time = await download_file(asset_url, request.node.name, "stability_upscaled.png")
    assert os.path.exists(upscaled_file_path)
    assert os.path.getsize(upscaled_file_path) > 0

    # 6. Print test summary
    timings = {
        "API Response Time": api_response_time,
        "Stability AI Processing": ai_processing_time,
        "Upscaled Download": upscaled_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": image_to_upload_url, "upscaled_asset_url": asset_url},
        "local_files": {"stability_upscaled.png": upscaled_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)



@pytest.mark.asyncio
async def test_generate_upscale_recraft(request):
    """Test: /generate/upscale endpoint with Recraft AI."""
    start_time = time.time()
    client_task_id = f"test-upscale-recraft-{uuid.uuid4()}"

    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/upscale"
    image_to_upload_url = "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"

    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")

    # 3. Call BFF endpoint
    request_data = {
        "task_id": client_task_id,
        "provider": "recraft",
        "input_image_asset_url": image_to_upload_url,
        "model": "crisp",
        "response_format": "url"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers=get_auth_headers())
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start
    print(f"🌐 API Response received in {api_response_time:.2f}s")

    task_id = result["task_id"]
    print(f"🆔 Task ID: {task_id}")

    # 4. Wait for Celery task completion
    polling_start = time.time()
    task_result_data = await wait_for_celery_task(task_id, "Recraft", total_timeout=180.0)
    ai_processing_time = time.time() - polling_start
    print(f"🤖 Recraft AI Processing completed in {ai_processing_time:.2f}s")

    # 5. Download and verify the result
    asset_url = task_result_data['asset_url']
    upscaled_file_path, upscaled_download_time = await download_file(asset_url, request.node.name, "recraft_upscaled.png")
    assert os.path.exists(upscaled_file_path)
    assert os.path.getsize(upscaled_file_path) > 0

    # 6. Print test summary
    timings = {
        "API Response Time": api_response_time,
        "Recraft AI Processing": ai_processing_time,
        "Upscaled Download": upscaled_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": image_to_upload_url, "upscaled_asset_url": asset_url},
        "local_files": {"recraft_upscaled.png": upscaled_file_path}
    }
    print_test_summary(request.node.name, client_task_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_upscale_endpoint_invalid_provider():
    """Test the /generate/upscale endpoint with an invalid provider."""
    print("\n🚀 Starting test: test_upscale_endpoint_invalid_provider")
    logger.info("Testing /generate/upscale endpoint with invalid provider...")
    
    endpoint = f"{BASE_URL}/generate/upscale"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            endpoint,
            headers=get_auth_headers(),
            json={
                "task_id": f"test-upscale-invalid-{uuid.uuid4()}",
                "provider": "invalid_provider",
                "input_image_asset_url": "http://example.com/image.png"
            }
        )
        
        assert response.status_code == 422
        response_data = response.json()
        assert "Input should be 'stability' or 'recraft'" in response_data["detail"][0]["msg"]
        
        print("✅ Invalid provider test passed")
        logger.info("✅ Invalid provider test passed")

@pytest.mark.asyncio
async def test_upscale_endpoint_missing_image_url():
    """Test the /generate/upscale endpoint with missing image URL."""
    print("\n🚀 Starting test: test_upscale_endpoint_missing_image_url")
    logger.info("Testing /generate/upscale endpoint with missing image URL...")
    
    endpoint = f"{BASE_URL}/generate/upscale"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            endpoint,
            headers=get_auth_headers(),
            json={
                "task_id": f"test-upscale-missing-url-{uuid.uuid4()}",
                "provider": "stability"
            }
        )
        
        assert response.status_code == 422  # Validation error
        print("✅ Missing image URL test passed")
        logger.info("✅ Missing image URL test passed") 