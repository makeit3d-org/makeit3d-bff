import httpx
import pytest
import os
import time
import logging
import base64 # Import base64 module
import uuid # Import uuid for generating unique file names
import asyncio

# Set test mode environment variables BEFORE importing any app modules
# This ensures that Celery workers also see these settings
os.environ["TEST_ASSETS_MODE"] = "True"

from app.schemas.generation_schemas import ImageToImageRequest
# Import Supabase client functions
from app.supabase_client import get_supabase_client, download_image_from_storage, create_signed_url
import app.supabase_handler as supabase_handler # Add supabase_handler import
# Import config settings and set test mode
from app.config import settings
# Remove these lines since we're now setting them via environment variables
# settings.test_assets_mode = True # Enable test assets mode - outputs to test folders

# Configure BASE_URL to work both inside Docker containers and from host machine
# When running in Docker Compose, services communicate using container names
# When running from host, we need to use localhost
BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
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
    download_start = time.time()
    
    attempts = 3  # Try up to 3 times
    for attempt in range(attempts):
        try:
            # First, try regular HTTP download (works for public URLs and signed URLs)
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
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
            if e.response.status_code in [401, 403] and settings.supabase_url in url:
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
                    logger.info(f"Successfully downloaded {file_name} via authenticated method in {download_time:.2f}s")
                    return file_path, download_time
                    
                except Exception as auth_error:
                    logger.error(f"Authenticated download also failed: {auth_error}")
                    # Continue to the retry logic below
            
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

# --- Helper function to wait for synchronous Celery tasks ---
async def wait_for_celery_task(celery_task_id: str, provider: str, poll_interval: int = 1, total_timeout: float = 300.0):
    """
    Wait for a synchronous Celery task to complete (for Stability, Recraft, Flux).
    These providers complete their work within the Celery task and don't require status polling.
    """
    from app.celery_worker import celery_app
    
    print(f"\n⏳ Waiting for {provider} Celery task {celery_task_id} to complete...")
    logger.info(f"Waiting for {provider} Celery task {celery_task_id} to complete...")
    start_time = time.time()
    
    celery_result = celery_app.AsyncResult(celery_task_id)
    
    while time.time() - start_time < total_timeout:
        if celery_result.ready():
            if celery_result.failed():
                error_info = str(celery_result.info) if celery_result.info else "Celery task failed without specific error info."
                error_msg = f"❌ {provider} Celery task {celery_task_id} failed: {error_info}"
                print(error_msg)
                logger.error(error_msg)
                pytest.fail(f"{provider} task {celery_task_id} failed: {error_info}")
            
            # Task completed successfully
            task_result_data = celery_result.result
            complete_msg = f"✅ {provider} Celery task {celery_task_id} completed!"
            print(complete_msg)
            logger.info(complete_msg)
            return task_result_data
        
        # Task still running, wait a bit
        await asyncio.sleep(poll_interval)
    
    # Timeout reached
    timeout_msg = f"⏰ {provider} Celery task {celery_task_id} timed out after {total_timeout} seconds"
    print(timeout_msg)
    logger.error(timeout_msg)
    pytest.fail(f"{provider} task {celery_task_id} timed out after {total_timeout} seconds")

# --- Helper function to poll task status ---
async def poll_task_status(task_id: str, service: str, poll_interval: int = 2, total_timeout: float = 300.0):
    status_url = f"{BASE_URL}/tasks/{task_id}/status?service={service.lower()}"
    print(f"\n📊 Polling {service} task {task_id} with total timeout {total_timeout}s...")
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
                
                # Log progress only if it changed - show in terminal and logs
                current_progress = status_data.get('progress', 0)
                if current_progress != last_progress:
                    progress_msg = f"📈 Task {task_id} progress: {current_progress}% ({status_data.get('status')})"
                    print(progress_msg)  # Terminal output
                    logger.info(progress_msg)  # Log output
                    last_progress = current_progress

                if status_data.get('status') == 'complete':
                    complete_msg = f"✅ Task {task_id} complete!"
                    print(complete_msg)
                    logger.info(complete_msg)
                    
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
                    error_msg = f"❌ Task {task_id} failed. Status data: {status_data}"
                    print(error_msg)
                    logger.error(error_msg)
                    pytest.fail(f"{service.capitalize()} task {task_id} failed.")
                
                # If task is still processing but 100% complete for Tripo, check if it has a model URL
                if service.lower() == 'tripoai' and status_data.get('progress') == 100:
                    if status_data.get('asset_url'):
                        complete_msg = f"✅ Task {task_id} at 100% with asset_url. Considering complete."
                        print(complete_msg)
                        logger.info(complete_msg)
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

# --- Helper function to extract bucket and path info ---
def extract_bucket_path_info(supabase_url: str) -> dict:
    """Extract bucket name and folder path from a Supabase URL."""
    try:
        # Parse URL like: https://[project].supabase.co/storage/v1/object/public/bucket_name/folder/path/file.ext
        # or signed URL: https://[project].supabase.co/storage/v1/object/sign/bucket_name/folder/path/file.ext?token=...
        
        if '/storage/v1/object/public/' in supabase_url:
            path_part = supabase_url.split('/storage/v1/object/public/', 1)[1]
        elif '/storage/v1/object/sign/' in supabase_url:
            # For signed URLs, strip the token part first
            url_without_token = supabase_url.split('?token=')[0] if '?token=' in supabase_url else supabase_url
            path_part = url_without_token.split('/storage/v1/object/sign/', 1)[1]
        else:
            return {"bucket": "unknown", "folder_path": "unknown", "file_name": "unknown", "full_path": "unknown"}
            
        parts = path_part.split('/', 2)
        bucket = parts[0] if len(parts) > 0 else "unknown"
        folder_path = parts[1] if len(parts) > 1 else ""
        file_name = parts[2] if len(parts) > 2 else ""
        
        return {
            "bucket": bucket,
            "folder_path": folder_path,
            "file_name": file_name,
            "full_path": f"{bucket}/{folder_path}/{file_name}" if folder_path else f"{bucket}/{file_name}"
        }
    except Exception as e:
        return {"bucket": f"parse_error: {str(e)}", "folder_path": "unknown", "file_name": "unknown", "full_path": "unknown"}

# --- Test Summary Function ---
def print_test_summary(test_name: str, client_task_id: str, start_time: float, timings: dict, locations: dict):
    """Print comprehensive test execution summary."""
    total_time = time.time() - start_time
    
    print("\n" + "="*80)
    print(f"🎯 TEST SUMMARY: {test_name}")
    print("="*80)
    print(f"📋 TASK ID: {client_task_id}")
    print("="*80)
    
    # Timing breakdown
    print("\n⏱️  EXECUTION TIMES:")
    print(f"   Total Test Time: {total_time:.2f}s")
    for phase, duration in timings.items():
        print(f"   {phase}: {duration:.2f}s")
    
    # File locations
    print("\n📁 FILE LOCATIONS:")
    
    if locations.get('database_records'):
        print("   Database Records:")
        for record_type, record_info in locations['database_records'].items():
            print(f"     {record_type}: {record_info}")
    
    if locations.get('supabase_storage'):
        print("   Supabase Storage:")
        for storage_type, url in locations['supabase_storage'].items():
            bucket_info = extract_bucket_path_info(url)
            print(f"     {storage_type}:")
            print(f"       URL: {url}")
            print(f"       Bucket: {bucket_info['bucket']}")
            print(f"       Folder Path: {bucket_info['folder_path']}")
            print(f"       File Name: {bucket_info['file_name']}")
            print(f"       Full Path: {bucket_info['full_path']}")
    
    if locations.get('local_files'):
        print("   Local Test Files:")
        for file_type, path in locations['local_files'].items():
            print(f"     {file_type}: {path}")
    
    if locations.get('api_endpoints'):
        print("   API Endpoints Used:")
        for endpoint, details in locations['api_endpoints'].items():
            print(f"     {endpoint}: {details}")
    
    print("\n" + "="*80)
    print("✅ TEST COMPLETED SUCCESSFULLY")
    print("="*80 + "\n")

# --- Test Endpoints ---

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
    
    # For image-to-image, we expect at least one generated image
    assert asset_url is not None
    logger.info(f"Received enhanced image Supabase URL: {asset_url}")

    # Download the generated enhanced image
    enhanced_image_file_path, enhanced_image_download_time = await download_file(asset_url, request.node.name, "enhanced_image.png")
    print(f"💾 Enhanced image downloaded in {enhanced_image_download_time:.2f}s")

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
        "Enhanced Image Download": enhanced_image_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": input_supabase_url, "enhanced_image_asset_url": asset_url},
        "local_files": {"enhanced_image.png": enhanced_image_file_path}
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

    # Poll for completion
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "recraft", total_timeout=180.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Recraft AI Processing completed in {ai_processing_time:.2f}s")

    asset_url = task_result_data['asset_url']
    enhanced_image_file_path, enhanced_image_download_time = await download_file(asset_url, request.node.name, "recraft_enhanced_image.png")

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "Recraft AI Processing": ai_processing_time,
        "Enhanced Image Download": enhanced_image_download_time
    }
    locations = {
        "supabase_storage": {"input_image_asset_url": input_supabase_url, "enhanced_image_asset_url": asset_url},
        "local_files": {"recraft_enhanced_image.png": enhanced_image_file_path}
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

    # Poll for completion
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "stability", total_timeout=120.0)
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

    # Poll for completion
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "recraft", total_timeout=120.0)
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
    task_result_data = await poll_task_status(celery_task_id, "tripoai", total_timeout=300.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Tripo AI Processing completed in {ai_processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME: {ai_processing_time:.2f}s")
    logger.info(f"Full task_result_data: {task_result_data}")

    model_url = task_result_data.get('asset_url') # Expecting 'asset_url' based on TaskStatusResponse schema

    assert model_url is not None, f"Model asset_url not found in response: {task_result_data}"
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
        response = await client.post(image_to_model_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result
    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Poll for task completion
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "tripoai", total_timeout=300.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Tripo AI Processing completed in {ai_processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME: {ai_processing_time:.2f}s")

    model_url = task_result_data.get('asset_url')

    assert model_url is not None, f"Model asset_url not found in response: {task_result_data}"
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
        "foreground_ratio": 0.85
    }

    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(image_to_model_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")

    # Poll for completion
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "stability", total_timeout=300.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Stability AI Processing completed in {ai_processing_time:.2f}s")

    model_url = task_result_data.get('asset_url')
    assert model_url is not None, f"Model asset_url not found in response: {task_result_data}"

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
async def test_generate_sketch_to_image(request):
    """Test 4.1: /generate/sketch-to-image endpoint (Stability AI)."""
    start_time = time.time()
    client_task_id = f"test-s2i-stability-{uuid.uuid4()}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Client Task ID: {client_task_id}")
    logger.info(f"TEST START: {start_time}")
    
    sketch_to_image_endpoint = f"{BASE_URL}/generate/sketch-to-image"
    
    # 1. Simulate client having a sketch image in their Supabase.
    # For the test, we download a public sketch, then upload it to our test Supabase area.
    public_sketch_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public/sketch-cat.jpg"
    logger.info(f"Running {request.node.name} for task_id: {client_task_id}. Using public sketch: {public_sketch_url}")

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

    request_data = {
        "task_id": client_task_id,
        "provider": "stability",
        "input_sketch_asset_url": input_sketch_supabase_url,
        "prompt": "Create a 3D model from this sketch",
        "control_strength": 0.8,
        "style_preset": "3d-model"
    }

    logger.info(f"Calling {sketch_to_image_endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient() as client:
        api_call_start = time.time()
        response = await client.post(sketch_to_image_endpoint, json=request_data)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    assert "celery_task_id" in result
    celery_task_id = result["celery_task_id"]
    print(f"🆔 Celery Task ID: {celery_task_id}")
    logger.info(f"Received Celery task_id: {celery_task_id}")

    # Poll for task completion
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "stability", total_timeout=300.0)
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Stability AI Processing completed in {ai_processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME: {ai_processing_time:.2f}s")

    asset_url = task_result_data.get('asset_url')

    assert asset_url is not None, f"Asset asset_url not found in response: {task_result_data}"
    logger.info(f"Received asset Supabase URL: {asset_url}")

    # Download the generated asset
    asset_file_path, asset_download_time = await download_file(asset_url, request.node.name, "sketch_result.png")
    print(f"💾 Asset downloaded in {asset_download_time:.2f}s")
    logger.info(f"Asset downloaded to: {asset_file_path}")
    
    assert os.path.exists(asset_file_path)
    assert os.path.getsize(asset_file_path) > 0

    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    logger.info(f"TOTAL TEST TIME: {total_test_time:.2f}s")

    # Test summary
    timings = {
        "Input Download": input_download_time,
        "Input Upload": upload_time,
        "API Response Time": api_response_time,
        "Stability AI Processing": ai_processing_time,
        "Asset Download": asset_download_time
    }
    locations = {
        "supabase_storage": {"input_sketch_asset_url": input_sketch_supabase_url, "asset_url": asset_url},
        "local_files": {"sketch_result.png": asset_file_path}
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

    # Poll for completion
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "stability", total_timeout=120.0)
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

    # Poll for completion
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "recraft", total_timeout=120.0)
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

    # Poll for task completion with extended timeout for multiview processing
    polling_start = time.time()
    task_result_data = await poll_task_status(celery_task_id, "tripoai", total_timeout=600.0)  # Extended timeout
    ai_processing_time = time.time() - polling_start
    
    print(f"🤖 Tripo AI Multiview Processing completed in {ai_processing_time:.2f}s")
    logger.info(f"TASK PROCESSING TIME (multiview): {ai_processing_time:.2f}s")

    model_url = task_result_data.get('asset_url')

    assert model_url is not None, f"Model asset_url not found in response: {task_result_data}"
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


@pytest.mark.asyncio
async def test_generate_image_inpaint(request):
    """Test 6.1: /generate/image-inpaint endpoint (Recraft AI)."""
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


 