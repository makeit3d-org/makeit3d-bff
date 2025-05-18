import logging
import base64

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
# Import the new Supabase client functions
from app.supabase_client import upload_image_to_storage, create_concept_image_record

logger = logging.getLogger(__name__)

# Define approximate rate limits (replace with official rates when known)
# Example: 10 requests per minute for OpenAI, 5 requests per minute for Tripo
# OPENAI_RATE_LIMIT = '10/m' # Keep commented out for now until we manage rate limits centrally
TRIPO_RATE_LIMIT = '5/m' # Keep commented out for now until we manage rate limits centrally

@celery_app.task(bind=True)
async def generate_openai_image_task(self, image_bytes: bytes, image_filename: str, request_data_dict: dict):
    """Celery task to call OpenAI image generation API, upload to Supabase, and store metadata."""
    logger.info(f"Celery task {self.request.id}: Starting OpenAI image generation and Supabase upload.")
    uploaded_image_urls = []
    task_id = self.request.id

    try:
        # Deserialize request data
        request_data = ImageToImageRequest(**request_data_dict)

        # --- OpenAI API Call ---
        openai_response = openai_client.generate_image_to_image( # Use the async client function directly
            image_bytes, image_filename, request_data
        )

        # OpenAI returns a list of objects with 'b64_json' for gpt-image-1 edit
        b64_images = [item["b64_json"] for item in openai_response.get("data", [])]

        logger.info(f"Celery task {task_id}: OpenAI image generation completed, processing {len(b64_images)} images.")

        # --- Supabase Upload and Database Record ---
        for i, b64_image in enumerate(b64_images):
            try:
                # Decode base64 to binary
                image_data = base64.b64decode(b64_image)

                # Generate a unique file name (e.g., task_id/image_index.png)
                # Assuming PNG format from OpenAI, might need adjustment if different
                file_name = f"{task_id}/{i}.png"

                # Upload to Supabase Storage (using the default 'concept_images' bucket)
                image_url = await upload_image_to_storage(file_name, image_data)
                logger.info(f"Celery task {task_id}: Uploaded image {i} to {image_url}")
                uploaded_image_urls.append(image_url)

                # Create database record
                # We can extract prompt and style from the request_data if available
                prompt = request_data.prompt
                style = request_data.style # Assuming style is part of ImageToImageRequest, adjust if needed
                await create_concept_image_record(task_id, image_url, prompt, style)
                logger.info(f"Celery task {task_id}: Created database record for image {i}.")

            except Exception as upload_e:
                logger.error(f"Celery task {task_id}: Failed to process and upload image {i}: {upload_e}", exc_info=True)
                # Decide how to handle partial failures - for now, log and continue
                # Alternatively, mark the entire task as failed or retry
                pass # Continue processing other images if one fails

        if not uploaded_image_urls:
             # If no images were successfully uploaded, raise an error
             raise Exception("No images were successfully uploaded to Supabase Storage.")

        logger.info(f"Celery task {task_id}: Finished processing and uploading images.")

        # Return the list of public URLs
        return {'image_urls': uploaded_image_urls}

    except Exception as e:
        logger.error(f"Celery task {task_id}: OpenAI task failed: {e}", exc_info=True)
        # Propagate the exception to mark the task as failed
        raise self.retry(exc=e, countdown=5, max_retries=3)

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