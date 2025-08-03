import httpx
import pytest
import os
import time
import logging
import uuid
import asyncio

# Set test mode environment variables BEFORE importing any app modules
os.environ["TEST_ASSETS_MODE"] = "True"

# Import Supabase handler for video operations
import app.supabase_handler as supabase_handler
from app.config import settings

# Configure BASE_URL to work both inside Docker containers and from host machine
BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
OUTPUTS_DIR = "./tests/outputs"

# Test API Key for authentication
TEST_API_KEY = os.environ.get("TEST_API_KEY", "makeit3d_test_sk_dev_001")

# Configure logging for tests
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure the outputs directory exists
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# --- Helper function for authenticated API calls ---
def get_auth_headers():
    """Get authentication headers for API calls."""
    return {"X-API-Key": TEST_API_KEY, "Content-Type": "application/json"}

# --- Helper function to download files ---
async def download_file(url: str, test_name: str, file_suffix: str):
    file_name = f"{test_name}_{file_suffix}"
    file_path = os.path.join(OUTPUTS_DIR, file_name)
    logger.info(f"Downloading {url} to {file_path}")
    download_start = time.time()
    
    attempts = 3  # Try up to 3 times
    for attempt in range(attempts):
        try:
            # First, try regular HTTP download (works for public URLs and signed URLs)
            async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for videos
                response = await client.get(url)
                response.raise_for_status()
                file_content = response.content
                file_size = len(file_content)
                logger.info(f"Downloaded file size: {file_size} bytes via HTTP client")
            
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
                f.write(file_content)
            
            download_time = time.time() - download_start
            logger.info(f"Successfully downloaded {file_name} in {download_time:.2f}s")
            return file_path, download_time
            
        except httpx.HTTPStatusError as e:
            # If we get 401/403 and this looks like our Supabase URL, try authenticated download
            if e.response.status_code in [401, 403] and settings.SUPABASE_URL in url:
                logger.info(f"HTTP {e.response.status_code} error for Supabase URL, trying authenticated download...")
                try:
                    file_content = await supabase_handler.fetch_asset_from_storage(url)
                    file_size = len(file_content)
                    logger.info(f"Downloaded file size: {file_size} bytes via authenticated method")
                    
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
                        f.write(file_content)
                    
                    download_time = time.time() - download_start
                    logger.info(f"Successfully downloaded {file_name} in {download_time:.2f}s via authenticated method")
                    return file_path, download_time
                    
                except Exception as auth_error:
                    logger.error(f"Authenticated download failed: {auth_error}")
                    if attempt < attempts - 1:
                        logger.info(f"Retrying download (attempt {attempt+2}/{attempts})...")
                        await asyncio.sleep(2)
                        continue
                    else:
                        pytest.fail(f"Both HTTP and authenticated download failed: {auth_error}")
            else:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                if attempt < attempts - 1:
                    logger.info(f"Retrying download (attempt {attempt+2}/{attempts})...")
                    await asyncio.sleep(2)
                    continue
                else:
                    pytest.fail(f"Download failed after {attempts} attempts: {e}")
                    
        except Exception as e:
            logger.error(f"Unexpected error during download: {e}")
            if attempt < attempts - 1:
                logger.info(f"Retrying download (attempt {attempt+2}/{attempts})...")
                await asyncio.sleep(2)
                continue
            else:
                pytest.fail(f"Download failed after {attempts} attempts: {e}")
    
    # This should never be reached, but just in case
    pytest.fail(f"Download failed after {attempts} attempts")

# --- Helper function for task status polling ---
async def poll_task_status(task_id: str, timeout: int = 600, poll_interval: int = 10):
    """Poll task status with timeout for video generation (videos take longer)."""
    status_endpoint = f"{BASE_URL}/tasks/{task_id}/status"
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(status_endpoint, headers=get_auth_headers())
                response.raise_for_status()
                result = response.json()
                
                status = result.get("status")
                logger.info(f"Task {task_id} status: {status}")
                
                if status == "complete" or status == "succeeded":
                    return result
                elif status == "failed":
                    error_msg = result.get("error", "Unknown error")
                    pytest.fail(f"Task failed: {error_msg}")
                
                # Continue polling
                await asyncio.sleep(poll_interval)
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Status check error: {e.response.status_code} - {e.response.text}")
                await asyncio.sleep(poll_interval)
    
    pytest.fail(f"Task {task_id} timed out after {timeout} seconds")

"""
@pytest.mark.asyncio
async def test_generate_text_to_video_basic(request):
    # Test 7.1: /generate/video endpoint (Replicate Kling v2.1) - Basic text-to-video.
    # COMMENTED OUT: Kling v2.1 only supports image-to-video, not pure text-to-video
    start_time = time.time()
    client_task_id = f"test-t2v-replicate-basic-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/video"
    prompt = "A cute animated cat playing with a ball of yarn in a cozy living room"
    
    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")
    
    # Test with basic parameters
    request_data = {
        "provider": "replicate",
        "prompt": prompt,
        "model": "kling-v2.1",
        "mode": "standard",  # 720p
        "duration": 5,  # 5 seconds
        "aspect_ratio": "16:9"
    }
    
    logger.info(f"Calling {endpoint} with JSON data: {request_data}")
    
    # Call the video generation endpoint
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers=get_auth_headers())
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start
    
    task_id = result["task_id"]
    print(f"📋 CELERY TASK ID: {task_id}")
    print(f"⏱️  API RESPONSE TIME: {api_response_time:.2f}s")
    logger.info(f"API call successful. Celery task ID: {task_id}")
    
    # Poll for completion (videos take much longer than images)
    print("⏳ Polling for video generation completion...")
    poll_start = time.time()
    
    final_result = await poll_task_status(task_id, timeout=600, poll_interval=15)  # 10 minutes max, check every 15s
    
    poll_time = time.time() - poll_start
    print(f"✅ VIDEO GENERATION COMPLETED in {poll_time:.2f}s")
    logger.info(f"Task completed in {poll_time:.2f}s")
    
    # Verify the result contains video URL
    assert "asset_url" in final_result, "Response should contain asset_url"
    video_url = final_result["asset_url"]
    
    print(f"🎬 Generated video URL: {video_url}")
    logger.info(f"Generated video URL: {video_url}")
    
    # Download the generated video
    video_path, download_time = await download_file(video_url, "test_generate_text_to_video_basic", "video.mp4")
    
    print(f"📥 VIDEO DOWNLOADED: {video_path} in {download_time:.2f}s")
    
    # Verify video file exists and has reasonable size (videos should be at least 100KB)
    assert os.path.exists(video_path), "Video file should exist"
    file_size = os.path.getsize(video_path)
    assert file_size > 100000, f"Video file should be larger than 100KB, got {file_size} bytes"
    
    total_time = time.time() - start_time
    print(f"🎯 TOTAL TEST TIME: {total_time:.2f}s")
    print(f"✅ Test completed successfully!")
    logger.info(f"Test completed successfully in {total_time:.2f}s")
"""

@pytest.mark.asyncio
async def test_generate_text_to_video_with_start_image(request):
    """Test 7.2: /generate/video endpoint (Replicate Kling v2.1) - With start image."""
    start_time = time.time()
    client_task_id = f"test-t2v-replicate-image-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/video"
    prompt = "The boy jumps up and down in excitement"
    
    # Download and upload a start image
    start_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"
    
    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")
    
    # 1. Download the public image
    input_download_start = time.time()
    async with httpx.AsyncClient() as client:
        image_response = await client.get(start_image_url)
        image_response.raise_for_status()
        image_content = image_response.content
        original_filename = start_image_url.split("/")[-1]
    input_download_time = time.time() - input_download_start
    
    print(f"📥 START IMAGE DOWNLOADED: {original_filename} in {input_download_time:.2f}s")
    logger.info(f"START IMAGE DOWNLOADED: {original_filename}")
    
    # 2. Upload the image to Supabase Storage (simulating client upload)
    upload_start = time.time()
    input_supabase_url = await supabase_handler.upload_asset_to_storage(
        task_id=client_task_id,
        asset_type_plural="test_inputs/video-generation",
        file_name=original_filename,
        asset_data=image_content,
        content_type="image/jpeg"
    )
    upload_time = time.time() - upload_start
    
    print(f"📤 START IMAGE UPLOADED: {input_supabase_url} in {upload_time:.2f}s")
    logger.info(f"START IMAGE UPLOADED: {input_supabase_url}")
    
    # Test with start image and pro mode
    request_data = {
        "provider": "replicate",
        "prompt": prompt,
        "model": "kling-v2.1",
        "mode": "standard",  # 720p
        "duration": 5,  # 5 seconds
        "start_image": input_supabase_url,
        "negative_prompt": "blurry, low quality, distorted",
        "aspect_ratio": "16:9"  # Vertical video
    }
    
    logger.info(f"Calling {endpoint} with JSON data: {request_data}")
    
    # Call the video generation endpoint
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers=get_auth_headers())
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start
    
    task_id = result["task_id"]
    print(f"📋 CELERY TASK ID: {task_id}")
    print(f"⏱️  API RESPONSE TIME: {api_response_time:.2f}s")
    logger.info(f"API call successful. Celery task ID: {task_id}")
    
    # Poll for completion (pro mode may take longer)
    print("⏳ Polling for video generation completion...")
    poll_start = time.time()
    
    final_result = await poll_task_status(task_id, timeout=900, poll_interval=20)  # 15 minutes max, check every 20s
    
    poll_time = time.time() - poll_start
    print(f"✅ VIDEO GENERATION COMPLETED in {poll_time:.2f}s")
    logger.info(f"Task completed in {poll_time:.2f}s")
    
    # Verify the result contains video URL
    assert "asset_url" in final_result, "Response should contain asset_url"
    video_url = final_result["asset_url"]
    
    print(f"🎬 Generated video URL: {video_url}")
    logger.info(f"Generated video URL: {video_url}")
    
    # Download the generated video
    video_path, download_time = await download_file(video_url, "test_generate_text_to_video_with_start_image", "video.mp4")
    
    print(f"📥 VIDEO DOWNLOADED: {video_path} in {download_time:.2f}s")
    
    # Verify video file exists and has reasonable size (pro mode videos should be larger)
    assert os.path.exists(video_path), "Video file should exist"
    file_size = os.path.getsize(video_path)
    assert file_size > 200000, f"Pro mode video file should be larger than 200KB, got {file_size} bytes"
    
    total_time = time.time() - start_time
    print(f"🎯 TOTAL TEST TIME: {total_time:.2f}s")
    print(f"✅ Test completed successfully!")
    logger.info(f"Test completed successfully in {total_time:.2f}s")

"""
@pytest.mark.asyncio
async def test_generate_text_to_video_10_seconds(request):
    # Test 7.3: /generate/video endpoint (Replicate Kling v2.1) - 10 second duration.
    # COMMENTED OUT: Excluding 10s test per user request
    start_time = time.time()
    client_task_id = f"test-t2v-replicate-10s-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/video"
    prompt = "A serene time-lapse of clouds moving across a mountain landscape at sunset, with birds flying in the distance"
    
    logger.info(f"Running {request.node.name} for task_id: {client_task_id}...")
    
    # Test with 10 second duration (more expensive)
    request_data = {
        "provider": "replicate",
        "prompt": prompt,
        "model": "kling-v2.1",
        "mode": "standard",  # 720p
        "duration": 10,  # 10 seconds
        "aspect_ratio": "1:1",  # Square format
        "negative_prompt": "people, buildings, text"
    }
    
    logger.info(f"Calling {endpoint} with JSON data: {request_data}")
    
    # Call the video generation endpoint
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers=get_auth_headers())
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start
    
    task_id = result["task_id"]
    print(f"📋 CELERY TASK ID: {task_id}")
    print(f"⏱️  API RESPONSE TIME: {api_response_time:.2f}s")
    logger.info(f"API call successful. Celery task ID: {task_id}")
    
    # Poll for completion (10-second videos take longer)
    print("⏳ Polling for video generation completion...")
    poll_start = time.time()
    
    final_result = await poll_task_status(task_id, timeout=900, poll_interval=20)  # 15 minutes max
    
    poll_time = time.time() - poll_start
    print(f"✅ VIDEO GENERATION COMPLETED in {poll_time:.2f}s")
    logger.info(f"Task completed in {poll_time:.2f}s")
    
    # Verify the result contains video URL
    assert "asset_url" in final_result, "Response should contain asset_url"
    video_url = final_result["asset_url"]
    
    print(f"🎬 Generated video URL: {video_url}")
    logger.info(f"Generated video URL: {video_url}")
    
    # Download the generated video
    video_path, download_time = await download_file(video_url, "test_generate_text_to_video_10_seconds", "video.mp4")
    
    print(f"📥 VIDEO DOWNLOADED: {video_path} in {download_time:.2f}s")
    
    # Verify video file exists and has reasonable size (10s videos should be larger than 5s)
    assert os.path.exists(video_path), "Video file should exist"
    file_size = os.path.getsize(video_path)
    assert file_size > 300000, f"10-second video file should be larger than 300KB, got {file_size} bytes"
    
    total_time = time.time() - start_time
    print(f"🎯 TOTAL TEST TIME: {total_time:.2f}s")
    print(f"✅ Test completed successfully!")
    logger.info(f"Test completed successfully in {total_time:.2f}s")
"""

@pytest.mark.asyncio 
async def test_generate_video_invalid_provider(request):
    """Test 7.4: /generate/video endpoint with invalid provider (should fail)."""
    start_time = time.time()
    client_task_id = f"test-t2v-invalid-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/generate/video"
    
    # Test with invalid provider
    request_data = {
        "provider": "invalid_provider",
        "prompt": "A test video",
        "model": "kling-v2.1",
        "mode": "standard",
        "duration": 5
    }
    
    logger.info(f"Calling {endpoint} with invalid provider: {request_data}")
    
    # Call should fail with 400 error
    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, json=request_data, headers=get_auth_headers())
        
        # Should return 400 error
        assert response.status_code == 400, f"Expected 400 error, got {response.status_code}"
        result = response.json()
        assert "detail" in result, "Error response should contain detail message"
        
        print(f"✅ Correctly rejected invalid provider: {result['detail']}")
        logger.info(f"Correctly rejected invalid provider: {result['detail']}")
    
    total_time = time.time() - start_time
    print(f"🎯 TOTAL TEST TIME: {total_time:.2f}s")
    print(f"✅ Test completed successfully!")
    logger.info(f"Test completed successfully in {total_time:.2f}s")