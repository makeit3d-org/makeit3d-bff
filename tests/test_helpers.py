import httpx
import pytest
import os
import time
import logging
import base64
import uuid
import asyncio

# Set test mode environment variables BEFORE importing any app modules
# This ensures that Celery workers also see these settings
os.environ["TEST_ASSETS_MODE"] = "True"

from app.schemas.generation_schemas import ImageToImageRequest
# Import Supabase client functions
from app.supabase_client import get_supabase_client, download_image_from_storage, create_signed_url
import app.supabase_handler as supabase_handler
# Import config settings and set test mode
from app.config import settings

# Configure BASE_URL to work both inside Docker containers and from host machine
# When running in Docker Compose, services communicate using container names
# When running from host, we need to use localhost
BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
OUTPUTS_DIR = "/tests/outputs"

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
async def wait_for_celery_task(task_id: str, provider: str, poll_interval: int = 1, total_timeout: float = 300.0):
    """
    Wait for a synchronous Celery task to complete (for Stability, Recraft, Flux).
    These providers complete their work within the Celery task and don't require status polling.
    """
    from app.celery_worker import celery_app
    
    print(f"\n⏳ Waiting for {provider} Celery task {task_id} to complete...")
    logger.info(f"Waiting for {provider} Celery task {task_id} to complete...")
    start_time = time.time()
    
    celery_result = celery_app.AsyncResult(task_id)
    
    while time.time() - start_time < total_timeout:
        if celery_result.ready():
            if celery_result.failed():
                error_info = str(celery_result.info) if celery_result.info else "Celery task failed without specific error info."
                error_msg = f"❌ {provider} Celery task {task_id} failed: {error_info}"
                print(error_msg)
                logger.error(error_msg)
                pytest.fail(f"{provider} task {task_id} failed: {error_info}")
            
            # Task completed successfully
            task_result_data = celery_result.result
            complete_msg = f"✅ {provider} Celery task {task_id} completed!"
            print(complete_msg)
            logger.info(complete_msg)
            return task_result_data
        
        # Task still running, wait a bit
        await asyncio.sleep(poll_interval)
    
    # Timeout reached
    timeout_msg = f"⏰ {provider} Celery task {task_id} timed out after {total_timeout} seconds"
    print(timeout_msg)
    logger.error(timeout_msg)
    pytest.fail(f"{provider} task {task_id} timed out after {total_timeout} seconds")

# --- Helper function to poll task status ---
async def poll_task_status(task_id: str, service: str, poll_interval: int = 2, total_timeout: float = 300.0):
    status_url = f"{BASE_URL}/tasks/{task_id}/status?service={service.lower()}"
    print(f"\n📊 Polling {service} task {task_id} with total timeout {total_timeout}s...")
    logger.info(f"Polling {service} task {task_id} with total timeout {total_timeout}s...")
    start_time = time.time()
    last_progress = -1
    
    # Headers with API key for authentication
    headers = {"X-API-Key": TEST_API_KEY}
    
    while time.time() - start_time < total_timeout:
        try:
            # Use a shorter timeout for individual polling requests
            async with httpx.AsyncClient(timeout=10.0) as client:
                status_response = await client.get(status_url, headers=headers)
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
                        status_response = await client.get(status_url, headers=headers)
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
        print(f"   {phase}: {duration}")
    
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