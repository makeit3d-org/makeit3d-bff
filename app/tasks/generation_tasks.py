import logging
import base64
import inspect # Import inspect
import asyncio # Import asyncio
import httpx # Add httpx import for error handling

from celery import Celery

from app.celery_worker import celery_app
from app.ai_clients import openai_client, tripo_client
from app.schemas.generation_schemas import (
    ImageToImageRequest,
    TextToModelRequest,
    ImageToModelRequest,
    SketchToModelRequest,
    RefineModelRequest,
    SelectConceptRequest
)
# Import the synchronous Supabase client functions and custom exceptions
from app.supabase_client import (
    sync_upload_image_to_storage, 
    sync_create_concept_image_record,
    SupabaseStorageError,
    SupabaseDBError
)
# Import settings
from app.config import settings

logger = logging.getLogger(__name__)

# Removed hardcoded BFF_BASE_URL
# BFF_BASE_URL = "http://localhost:8000"

# Define approximate rate limits (replace with official rates when known)
# Example: 10 requests per minute for OpenAI, 5 requests per minute for Tripo
# OPENAI_RATE_LIMIT = '10/m' # Keep commented out for now until we manage rate limits centrally
TRIPO_RATE_LIMIT = '5/m' # Keep commented out for now until we manage rate limits centrally

# Custom exception for Celery tasks to ensure serializable errors
class CeleryTaskException(Exception):
    pass

# Convert task to non-async function that runs the async function via asyncio.run
@celery_app.task(bind=True)
def generate_openai_image_task(self, image_bytes: bytes, image_filename: str, request_data_dict: dict):
    """Celery task to call OpenAI image generation API, upload to Supabase, and store metadata."""
    task_id = self.request.id
    logger.info(f"Celery task {task_id}: Starting OpenAI image generation and Supabase upload.")
    
    # Define the async function that will be run
    async def process_openai_image():
        uploaded_image_download_urls = []
        
        try:
            request_data = ImageToImageRequest(**request_data_dict)

            openai_response = await openai_client.generate_image_to_image(
                image_bytes, image_filename, request_data
            )

            if inspect.iscoroutine(openai_response):
                logger.error(f"Celery task {task_id}: DEBUG CHECK FAILED - openai_response IS A COROUTINE AFTER AWAIT!")
                # This should not happen if openai_client.generate_image_to_image is correctly awaited and returns data
                raise CeleryTaskException(f"Internal error: OpenAI response was a coroutine.")

            b64_images = [item["b64_json"] for item in openai_response.get("data", [])]
            logger.info(f"Celery task {task_id}: OpenAI image generation completed, processing {len(b64_images)} images.")

            bucket_name = "concept-images"
            for i, b64_image in enumerate(b64_images):
                current_image_bytes = base64.b64decode(b64_image)
                file_name_in_bucket = f"{task_id}/{i}.png"

                # Upload to Supabase Storage using sync_upload_image_to_storage
                # We're in an async function, so use asyncio.to_thread for sync operations
                logger.info(f"Celery task {task_id}: Attempting to upload {file_name_in_bucket} to Supabase.")
                file_path = await asyncio.to_thread(
                    sync_upload_image_to_storage,
                    file_name_in_bucket, 
                    current_image_bytes, 
                    bucket_name
                )
                logger.info(f"Celery task {task_id}: Uploaded image {i} to {bucket_name}/{file_path}")

                download_url = f"{settings.bff_base_url}/images/{bucket_name}/{file_path}"
                uploaded_image_download_urls.append(download_url)

                # Create database record using asyncio.to_thread
                logger.info(f"Celery task {task_id}: Attempting to create DB record for {file_name_in_bucket}.")
                await asyncio.to_thread(
                    sync_create_concept_image_record,
                    task_id, 
                    download_url, 
                    bucket_name, 
                    request_data.prompt, 
                    request_data.style
                )
                logger.info(f"Celery task {task_id}: Created database record for image {i}.")

            if not uploaded_image_download_urls:
                raise CeleryTaskException("No images were successfully processed and uploaded after OpenAI generation.")

            logger.info(f"Celery task {task_id}: Finished processing and uploading images.")
            return {'image_urls': uploaded_image_download_urls}

        except httpx.HTTPStatusError as e_http:
            err_msg = f"HTTP error during OpenAI call: {e_http.response.status_code} - {getattr(e_http.response, 'text', 'No text')}"
            logger.error(f"Celery task {task_id}: {err_msg}", exc_info=True)
            raise CeleryTaskException(err_msg) # Re-raise as a simple, serializable exception

        except (SupabaseStorageError, SupabaseDBError) as e_supabase:
            err_msg = f"Supabase client error: {type(e_supabase).__name__} - {str(e_supabase)}"
            logger.error(f"Celery task {task_id}: {err_msg}", exc_info=True)
            raise CeleryTaskException(err_msg)
            
        except Exception as e_unhandled:
            err_msg = f"Unexpected error in OpenAI task: {type(e_unhandled).__name__} - {str(e_unhandled)}"
            logger.error(f"Celery task {task_id}: {err_msg}", exc_info=True)
            # Check if the unhandled exception or its arguments contain a coroutine for debugging
            if inspect.iscoroutine(e_unhandled) or any(inspect.iscoroutine(arg) for arg in e_unhandled.args if arg is not None):
                logger.error(f"Celery task {task_id}: The unhandled exception or its args contained a coroutine: {e_unhandled}")
                # Ensure the message is simple if it was a coroutine itself
                if inspect.iscoroutine(e_unhandled):
                    err_msg = f"Unexpected error in OpenAI task: Unhandled exception was a coroutine object."
            raise CeleryTaskException(err_msg)
            
    # Use a synchronous try/except block to handle any issues with the async function
    try:
        # Create a new event loop for this task to avoid conflicts with Celery's event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(process_openai_image())
        finally:
            loop.close()
    except Exception as e:
        # Handle any exceptions from running the async function
        logger.error(f"Celery task {task_id}: Error running async function: {type(e).__name__} - {str(e)}", exc_info=True)
        # Don't use self.retry as it might cause serialization issues with coroutines
        raise CeleryTaskException(f"Error running OpenAI task: {str(e)}")

@celery_app.task(bind=True, rate_limit=TRIPO_RATE_LIMIT)
def generate_tripo_text_to_model_task(self, request_data_dict: dict):
    """Celery task to call Tripo AI text-to-model endpoint."""
    logger.info(f"Celery task {self.request.id}: Starting Tripo AI text-to-model.")
    try:
        request_data = TextToModelRequest(**request_data_dict)
        tripo_response = tripo_client.generate_text_to_model(request_data)
        task_id = tripo_response["data"]["task_id"]
        logger.info(f"Celery task {self.request.id}: Initiated Tripo AI text-to-model task with ID: {task_id}")
        # Return the Tripo task ID. The status endpoint will poll Tripo directly.
        return {'tripo_task_id': task_id}
    except Exception as e:
        logger.error(f"Celery task {self.request.id}: Tripo AI text-to-model failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=5, max_retries=3)

@celery_app.task(bind=True, rate_limit=TRIPO_RATE_LIMIT)
def generate_tripo_image_to_model_task(self, request_data_dict: dict):
    """Celery task to call Tripo AI multiview-to-model endpoint."""
    logger.info(f"Celery task {self.request.id}: Starting Tripo AI image-to-model (multiview).")
    try:
        request_data = ImageToModelRequest(**request_data_dict)
        tripo_response = tripo_client.generate_image_to_model(request_data)
        task_id = tripo_response["data"]["task_id"]
        logger.info(f"Celery task {self.request.id}: Initiated Tripo AI image-to-model (multiview) task with ID: {task_id}")
        return {'tripo_task_id': task_id}
    except Exception as e:
        logger.error(f"Celery task {self.request.id}: Tripo AI image-to-model (multiview) failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=5, max_retries=3)

@celery_app.task(bind=True, rate_limit=TRIPO_RATE_LIMIT)
def generate_tripo_sketch_to_model_task(self, request_data_dict: dict):
    """Celery task to call Tripo AI image-to-model endpoint (for sketches)."""
    logger.info(f"Celery task {self.request.id}: Starting Tripo AI sketch-to-model.")
    try:
        request_data = SketchToModelRequest(**request_data_dict)
        tripo_response = tripo_client.generate_sketch_to_model(request_data)
        task_id = tripo_response["data"]["task_id"]
        logger.info(f"Celery task {self.request.id}: Initiated Tripo AI sketch-to-model task with ID: {task_id}")
        return {'tripo_task_id': task_id}
    except Exception as e:
        logger.error(f"Celery task {self.request.id}: Tripo AI sketch-to-model failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=5, max_retries=3)

@celery_app.task(bind=True, rate_limit=TRIPO_RATE_LIMIT)
def generate_tripo_refine_model_task(self, request_data_dict: dict):
    """Celery task to call Tripo AI refine-model endpoint."""
    logger.info(f"Celery task {self.request.id}: Starting Tripo AI refine-model.")
    try:
        request_data = RefineModelRequest(**request_data_dict)
        tripo_response = tripo_client.refine_model(request_data)
        task_id = tripo_response["data"]["task_id"]
        logger.info(f"Celery task {self.request.id}: Initiated Tripo AI refine-model task with ID: {task_id}")
        return {'tripo_task_id': task_id}
    except Exception as e:
        logger.error(f"Celery task {self.request.id}: Tripo AI refine-model failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=5, max_retries=3)

@celery_app.task(bind=True, rate_limit=TRIPO_RATE_LIMIT)
def generate_tripo_select_concept_task(self, request_data_dict: dict):
    """Celery task to handle selection of a concept and initiate Tripo 3D generation."""
    logger.info(f"Celery task {self.request.id}: Starting Tripo AI from selected concept.")
    try:
        request_data = SelectConceptRequest(**request_data_dict)
        # This calls the sketch-to-model client function, as it expects a single image URL
        tripo_response = tripo_client.generate_sketch_to_model(request_data)
        task_id = tripo_response["data"]["task_id"]
        logger.info(f"Celery task {self.request.id}: Initiated Tripo AI task from concept with ID: {task_id}")
        return {'tripo_task_id': task_id}
    except Exception as e:
        logger.error(f"Celery task {self.request.id}: Tripo AI from concept failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=5, max_retries=3)

# Note: The following tasks for polling status are now handled directly by the router
# They are kept here as comments for reference if needed in the future.

# @celery_app.task(bind=True)
# def poll_openai_image_status_task(self, task_id: str):
#     logger.info(f"Polling OpenAI image task status for {task_id}")
#     # This task is effectively synchronous as OpenAI returns results immediately.
#     # The polling logic is handled in the router, which retrieves the result.
#     # This placeholder task could be used for more complex polling if needed.
#     # return openai_client.get_task_status(task_id)
#     pass

# @celery_app.task(bind=True)
# def poll_tripo_task_status_task(self, tripo_task_id: str):
#     logger.info(f"Polling Tripo AI task status for {tripo_task_id}")
#     # This task would poll the Tripo AI status endpoint
#     # status_response = tripo_client.get_task_status(tripo_task_id)
#     # return status_response
#     pass 