import logging
import base64
import inspect # Import inspect
import asyncio # Import asyncio
import httpx # Add httpx import for error handling
from typing import Dict, Any, List

from celery import Celery

from app.celery_worker import celery_app
from app.ai_clients import openai_client, tripo_client
from app.ai_clients.stability_client import stability_client
from app.ai_clients.recraft_client import recraft_client
from app.schemas.generation_schemas import (
    ImageToImageRequest,
    TextToImageRequest,
    TextToModelRequest,
    ImageToModelRequest,
    SketchToImageRequest,
    RefineModelRequest,
    RemoveBackgroundRequest,
    ImageInpaintRequest,
    SearchAndRecolorRequest
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
import app.supabase_handler as supabase_handler # New Supabase handler

logger = logging.getLogger(__name__)

# Removed hardcoded BFF_BASE_URL
# BFF_BASE_URL = "http://localhost:8000"

# Define approximate rate limits (replace with official rates when known)
# Example: 10 requests per minute for OpenAI, 5 requests per minute for Tripo
# OPENAI_RATE_LIMIT = '10/m' # Keep commented out for now until we manage rate limits centrally
# TRIPO_RATE_LIMIT = '5/m' # Keep commented out for now until we manage rate limits centrally -> REMOVED

# Custom exception for Celery tasks to ensure serializable errors
class CeleryTaskException(Exception):
    pass

# Convert task to non-async function that runs the async function via asyncio.run
@celery_app.task(bind=True, rate_limit=settings.CELERY_OPENAI_TASK_RATE_LIMIT)
def generate_openai_image_task(self, concept_image_db_id: int, image_bytes: bytes, original_filename: str, request_data_dict: dict):
    """Celery task to call OpenAI image generation (text-to-image or image-to-image), upload to Supabase, and update the DB record."""
    # client_task_id is the overall task_id provided by the client, used for folder structures etc.
    client_task_id = request_data_dict.get("task_id")
    celery_task_id = self.request.id # This is Celery's internal task ID
    
    # Determine operation type based on whether image_bytes is provided
    is_text_to_image = not image_bytes
    operation_type = "text-to-image" if is_text_to_image else "image-to-image"
    
    logger.info(f"Celery task {celery_task_id} for DB record {concept_image_db_id} (Client Task ID: {client_task_id}): Starting OpenAI {operation_type}.")
    
    async def process_openai_image():
        uploaded_supabase_urls = []
        final_status = "failed" # Default to failed, update on success
        error_message = None
        
        try:
            # Create appropriate request data based on operation type
            if is_text_to_image:
                request_data = TextToImageRequest(**request_data_dict)
            else:
                request_data = ImageToImageRequest(**request_data_dict)

            # Update DB record to 'processing'
            await supabase_handler.update_concept_image_record(
                task_id=client_task_id, # Use client_task_id for identification if needed
                concept_image_id=concept_image_db_id,
                status="processing",
                # ai_service_task_id is already set by the router to celery_task_id
            )
            logger.info(f"Celery task {celery_task_id}: Updated DB record {concept_image_db_id} status to 'processing'.")

            # Call appropriate OpenAI method based on operation type
            if is_text_to_image:
                openai_response = await openai_client.generate_text_to_image(request_data)
            else:
                openai_response = await openai_client.generate_image_to_image(
                    image_bytes, original_filename, request_data
                )

            b64_images = [item.get("b64_json") for item in openai_response.get("data", []) if item.get("b64_json")]
            if not b64_images:
                error_message = f"OpenAI {operation_type} did not return any images."
                logger.error(f"Celery task {celery_task_id}: {error_message}")
                raise CeleryTaskException(error_message)

            logger.info(f"Celery task {celery_task_id}: OpenAI {operation_type} complete, processing {len(b64_images)} images.")

            for i, b64_image in enumerate(b64_images):
                try:
                    current_image_bytes = base64.b64decode(b64_image)
                    # Filename for Supabase storage, e.g., "0.png", "1.png"
                    # Path construction (concepts/client_task_id/0.png) is handled by upload_asset_to_storage
                    file_name_in_bucket = f"{i}.png" 
                    
                    logger.info(f"Celery task {celery_task_id}: Uploading image {i} ({file_name_in_bucket}) to Supabase.")
                    
                    supabase_url = await supabase_handler.upload_asset_to_storage(
                        task_id=client_task_id, 
                        asset_type_plural=supabase_handler.get_asset_type_for_concepts(),
                        file_name=file_name_in_bucket,
                        asset_data=current_image_bytes,
                        content_type="image/png"
                    )
                    uploaded_supabase_urls.append(supabase_url)
                    logger.info(f"Celery task {celery_task_id}: Uploaded image {i} to {supabase_url}")

                    # If this is the first image (or only one if n=1), update the main DB record.
                    # The initial DB record (concept_image_db_id) is intended for one primary concept image.
                    # If n > 1, additional images are uploaded, but only the first updates this specific record's asset_url.
                    # A more robust solution for n > 1 might involve creating separate DB records for each,
                    # or storing a list of URLs. This matches the simplified sync path for now.
                    if i == 0:
                        await supabase_handler.update_concept_image_record(
                            task_id=client_task_id,
                            concept_image_id=concept_image_db_id,
                            asset_url=supabase_url, # Set the asset_url for the primary/first image
                            status="complete", # Set status to complete
                            # Other fields like prompt, style are already set or can be re-set if needed
                            prompt=request_data.prompt,
                            style=request_data.style,
                        )
                        final_status = "complete" # Mark as complete if at least one image processed successfully
                        logger.info(f"Celery task {celery_task_id}: Updated DB record {concept_image_db_id} with asset_url {supabase_url} and status 'complete'.")
                
                except Exception as upload_exc:
                    # Log error for this specific image upload, but continue if others might succeed
                    logger.error(f"Celery task {celery_task_id}: Failed to upload image {i} for DB record {concept_image_db_id}: {upload_exc}", exc_info=True)
                    # If this was the primary image (i==0), the final_status will remain 'failed' unless a subsequent one succeeds (not current logic for i==0)
                    # For now, if the i==0 upload fails, the overall task for this record is effectively failed.
                    if i == 0:
                        error_message = f"Failed to upload primary image: {upload_exc}"
                        # No need to raise here, the outer try/except will handle final DB update
                        break # Stop processing further images if the primary one fails to upload

            if not uploaded_supabase_urls: # This means either no images returned or all uploads failed
                if not error_message: error_message = "No images were successfully uploaded."
                logger.error(f"Celery task {celery_task_id}: {error_message}")
                # Ensure CeleryTaskException is raised if we haven't already from OpenAI returning no images
                if not isinstance(error_message, CeleryTaskException): # Check if already raised
                     raise CeleryTaskException(error_message)

            logger.info(f"Celery task {celery_task_id}: Finished processing. Final status for DB record {concept_image_db_id} will be '{final_status}'.")
            # The actual return value for Celery might be simple, as main state is in DB
            return {'status': final_status, 'image_urls': uploaded_supabase_urls, 'db_record_id': concept_image_db_id}

        except httpx.HTTPStatusError as e_http:
            error_message = f"HTTP error during OpenAI {operation_type} call: {e_http.response.status_code} - {getattr(e_http.response, 'text', 'No text')}"
            logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: {error_message}", exc_info=True)
            final_status = "failed"
        except supabase_handler.SupabaseStorageError as e_sb_storage:
            error_message = f"Supabase Storage error: {str(e_sb_storage)}"
            logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: {error_message}", exc_info=True)
            final_status = "failed"
        except supabase_handler.SupabaseDBError as e_sb_db:
            error_message = f"Supabase DB error: {str(e_sb_db)}"
            logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: {error_message}", exc_info=True)
            final_status = "failed"
        except CeleryTaskException as e_celery_task: # Catch our own specific exception
            error_message = str(e_celery_task)
            logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: CeleryTaskException: {error_message}", exc_info=True)
            final_status = "failed" # Or a more specific status based on error_message
        except Exception as e_unhandled:
            error_message = f"Unexpected error: {type(e_unhandled).__name__} - {str(e_unhandled)}"
            logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: {error_message}", exc_info=True)
            final_status = "failed"
        
        # Ensure DB record is updated with the final status if an error occurred
        if final_status != "complete":
            try:
                await supabase_handler.update_concept_image_record(
                    task_id=client_task_id,
                    concept_image_id=concept_image_db_id,
                    status=final_status,
                    # Optionally add error_message to a metadata field if schema supports it
                    # metadata={"error": error_message} 
                )
                logger.info(f"Celery task {celery_task_id}: Updated DB record {concept_image_db_id} status to '{final_status}'.")
            except Exception as db_update_e:
                logger.error(f"Celery task {celery_task_id}: CRITICAL - Failed to update DB record {concept_image_db_id} to '{final_status}' after error: {db_update_e}", exc_info=True)
        
        if error_message and not isinstance(error_message, CeleryTaskException):
             # Re-raise to make Celery aware of the failure if not already a CeleryTaskException
            raise CeleryTaskException(error_message)
        elif isinstance(error_message, CeleryTaskException): # Already a CeleryTaskException
            raise error_message

    # Synchronous wrapper to run the async processing logic
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(process_openai_image())
        finally:
            loop.close()
    except Exception as e: # This will catch CeleryTaskException re-raised from process_openai_image
        logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: Final error state: {type(e).__name__} - {str(e)}", exc_info=True)
        # Celery will mark the task as failed if an exception is raised here.
        # No need for self.retry unless specific retry logic is desired for certain exceptions.
        raise # Re-raise the exception to ensure Celery sees it as a failure

@celery_app.task(bind=True)
def generate_tripo_text_to_model_task(self, model_db_id: str, request_data_dict: dict):
    """Celery task to call Tripo AI text-to-model, handle polling, download, upload to Supabase, and update the DB record."""
    
    client_task_id = request_data_dict.get("task_id")
    celery_task_id = self.request.id
    
    logger.info(f"Celery task {celery_task_id} for DB record {model_db_id} (Client Task ID: {client_task_id}): Starting Tripo text-to-model.")
    
    async def process_tripo_request():
        final_status = "failed"
        error_message = None
        tripo_task_id = None
        
        try:
            request_data = TextToModelRequest(**request_data_dict)

            # Update DB record to 'processing'
            await supabase_handler.update_model_record(
                task_id=client_task_id,
                model_id=model_db_id,
                status="processing",
            )
            logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} status to 'processing'.")

            # Call Tripo AI
            tripo_response = await tripo_client.generate_text_to_model(request_data)
            tripo_task_id = tripo_response.get("data", {}).get("task_id")
            
            if not tripo_task_id:
                error_message = "Failed to get Tripo AI task ID."
                logger.error(f"Celery task {celery_task_id}: {error_message}")
                raise CeleryTaskException(error_message)

            logger.info(f"Celery task {celery_task_id}: Got Tripo AI task ID: {tripo_task_id}")

            # Update DB record with Tripo task ID
            await supabase_handler.update_model_record(
                task_id=client_task_id,
                model_id=model_db_id,
                ai_service_task_id=tripo_task_id,
                status="processing",
            )

            # Wait for completion and get result - implement proper polling loop
            max_polls = 180  # 3 minutes with 1-second intervals
            poll_count = 0
            
            while poll_count < max_polls:
                tripo_response = await tripo_client.poll_tripo_task_status(tripo_task_id)
                normalized_result = tripo_client.normalize_tripo_status(tripo_response)
                
                task_status = normalized_result.get("status")
                progress = normalized_result.get("progress", 0)
                
                logger.info(f"Celery task {celery_task_id}: Tripo task {tripo_task_id} status: {task_status}, progress: {progress}%")
                
                if task_status == "complete":
                    result_url = normalized_result.get("result_url")
                    if not result_url:
                        error_message = "Tripo AI task complete but no result URL."
                        logger.error(f"Celery task {celery_task_id}: {error_message}")
                        raise CeleryTaskException(error_message)

                    # Download from Tripo's temporary URL
                    logger.info(f"Celery task {celery_task_id}: Downloading model from {result_url}")
                    async with httpx.AsyncClient() as http_client:
                        dl_response = await http_client.get(result_url, timeout=settings.TRIPO_DOWNLOAD_TIMEOUT_SECONDS)
                        dl_response.raise_for_status()
                        model_data_bytes = dl_response.content

                    # Upload to our Supabase
                    final_asset_url = await supabase_handler.upload_asset_to_storage(
                        task_id=client_task_id,
                        asset_type_plural=supabase_handler.get_asset_type_for_models(),
                        file_name="model.glb",
                        asset_data=model_data_bytes,
                        content_type="model/gltf-binary"
                    )

                    # Update DB record with final URL and complete status
                    await supabase_handler.update_model_record(
                        task_id=client_task_id,
                        model_id=model_db_id,
                        asset_url=final_asset_url,
                        status="complete",
                        ai_service_task_id=tripo_task_id,
                        prompt=request_data.prompt,
                        style=request_data.style
                    )

                    final_status = "complete"
                    logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} with final URL and status 'complete'.")
                    
                    return {
                        'status': final_status,
                        'result_url': final_asset_url,
                        'db_record_id': model_db_id,
                        'client_task_id': client_task_id,
                        'tripo_task_id': tripo_task_id
                    }
                elif task_status in ["failed", "cancelled", "unknown"]:
                    error_message = f"Tripo AI task failed with status: {task_status}"
                    logger.error(f"Celery task {celery_task_id}: {error_message}")
                    raise CeleryTaskException(error_message)
                
                # Task is still pending or processing, wait and poll again
                poll_count += 1
                await asyncio.sleep(1)
            
            # If we reach here, polling timed out
            error_message = f"Tripo AI task polling timed out after {max_polls} polls"
            logger.error(f"Celery task {celery_task_id}: {error_message}")
            raise CeleryTaskException(error_message)

        except httpx.HTTPStatusError as e_http:
            error_message = f"HTTP error during Tripo call: {e_http.response.status_code} - {getattr(e_http.response, 'text', 'No text')}"
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: {error_message}", exc_info=True)
            final_status = "failed"
        except CeleryTaskException as e_celery_task:
            error_message = str(e_celery_task)
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: CeleryTaskException: {error_message}", exc_info=True)
            final_status = "failed"
        except Exception as e_unhandled:
            error_message = f"Unexpected error: {type(e_unhandled).__name__} - {str(e_unhandled)}"
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: {error_message}", exc_info=True)
            final_status = "failed"
        
        # Ensure DB record is updated with the final status if an error occurred
        if final_status != "complete":
            try:
                await supabase_handler.update_model_record(
                    task_id=client_task_id,
                    model_id=model_db_id,
                    status=final_status,
                    ai_service_task_id=tripo_task_id
                )
                logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} status to '{final_status}'.")
            except Exception as db_update_e:
                logger.error(f"Celery task {celery_task_id}: CRITICAL - Failed to update DB record {model_db_id} to '{final_status}' after error: {db_update_e}", exc_info=True)
        
        if error_message:
            raise CeleryTaskException(error_message)

    # Synchronous wrapper to run the async processing logic
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(process_tripo_request())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: Final error state: {type(e).__name__} - {str(e)}", exc_info=True)
        raise

@celery_app.task(bind=True)
def generate_tripo_image_to_model_task(self, model_db_id: str, image_bytes_list: list[bytes], original_filenames: list[str], request_data_dict: dict):
    """Celery task to call Tripo AI image-to-model (multiview) and update DB with Tripo task ID."""
    client_task_id = request_data_dict.get("task_id")
    celery_task_id = self.request.id
    logger.info(f"Celery task {celery_task_id} for DB record {model_db_id} (Client Task ID: {client_task_id}): Starting Tripo AI image-to-model (multiview).")
    
    async def process_tripo_request():
        final_status = "failed"
        tripo_task_id = None
        error_message = None

        try:
            request_data = ImageToModelRequest(**request_data_dict)

            await supabase_handler.update_model_record(
                task_id=client_task_id,
                model_id=model_db_id,
                status="processing",
            )
            logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} status to 'processing'.")

            # Call Tripo AI with image bytes
            tripo_response = await tripo_client.generate_image_to_model(
                image_files_data=image_bytes_list,
                image_filenames=original_filenames,
                request_model=request_data 
            )
            
            tripo_task_id = tripo_response.get("data", {}).get("task_id")
            if not tripo_task_id:
                error_message = "Tripo AI (image-to-model) did not return a valid task ID."
                logger.error(f"Celery task {celery_task_id}: {error_message}")
                raise CeleryTaskException(error_message)

            logger.info(f"Celery task {celery_task_id}: Got Tripo AI task ID: {tripo_task_id}")

            await supabase_handler.update_model_record(
                task_id=client_task_id,
                model_id=model_db_id,
                ai_service_task_id=tripo_task_id,
                status="processing"
            )

            # Wait for completion and get result - implement proper polling loop
            max_polls = 180  # 3 minutes with 1-second intervals
            poll_count = 0
            
            while poll_count < max_polls:
                tripo_response = await tripo_client.poll_tripo_task_status(tripo_task_id)
                normalized_result = tripo_client.normalize_tripo_status(tripo_response)
                
                task_status = normalized_result.get("status")
                progress = normalized_result.get("progress", 0)
                
                logger.info(f"Celery task {celery_task_id}: Tripo task {tripo_task_id} status: {task_status}, progress: {progress}%")
                
                if task_status == "complete":
                    result_url = normalized_result.get("result_url")
                    if not result_url:
                        error_message = "Tripo AI task complete but no result URL."
                        logger.error(f"Celery task {celery_task_id}: {error_message}")
                        raise CeleryTaskException(error_message)

                    # Download from Tripo's temporary URL
                    logger.info(f"Celery task {celery_task_id}: Downloading model from {result_url}")
                    async with httpx.AsyncClient() as http_client:
                        dl_response = await http_client.get(result_url, timeout=settings.TRIPO_DOWNLOAD_TIMEOUT_SECONDS)
                        dl_response.raise_for_status()
                        model_data_bytes = dl_response.content

                    # Upload to our Supabase
                    final_asset_url = await supabase_handler.upload_asset_to_storage(
                        task_id=client_task_id,
                        asset_type_plural=supabase_handler.get_asset_type_for_models(),
                        file_name="model.glb",
                        asset_data=model_data_bytes,
                        content_type="model/gltf-binary"
                    )

                    # Update DB record with final URL and complete status
                    await supabase_handler.update_model_record(
                        task_id=client_task_id,
                        model_id=model_db_id,
                        asset_url=final_asset_url,
                        status="complete",
                        ai_service_task_id=tripo_task_id,
                        prompt=request_data.prompt,
                        style=request_data.style
                    )

                    final_status = "complete"
                    logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} with final URL and status 'complete'.")
                    
                    return {
                        'status': final_status,
                        'result_url': final_asset_url,
                        'db_record_id': model_db_id,
                        'client_task_id': client_task_id,
                        'tripo_task_id': tripo_task_id
                    }
                elif task_status in ["failed", "cancelled", "unknown"]:
                    error_message = f"Tripo AI task failed with status: {task_status}"
                    logger.error(f"Celery task {celery_task_id}: {error_message}")
                    raise CeleryTaskException(error_message)
                
                # Task is still pending or processing, wait and poll again
                poll_count += 1
                await asyncio.sleep(1)
            
            # If we reach here, polling timed out
            error_message = f"Tripo AI task polling timed out after {max_polls} polls"
            logger.error(f"Celery task {celery_task_id}: {error_message}")
            raise CeleryTaskException(error_message)

        except httpx.HTTPStatusError as e_http:
            error_message = f"HTTP error during Tripo call: {e_http.response.status_code} - {getattr(e_http.response, 'text', 'No text')}"
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: {error_message}", exc_info=True)
            final_status = "failed"
        except CeleryTaskException as e_celery_task:
            error_message = str(e_celery_task)
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: CeleryTaskException: {error_message}", exc_info=True)
            final_status = "failed"
        except Exception as e_unhandled:
            error_message = f"Unexpected error: {type(e_unhandled).__name__} - {str(e_unhandled)}"
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: {error_message}", exc_info=True)
            final_status = "failed"

        if final_status != "complete":
            try:
                await supabase_handler.update_model_record(
                    task_id=client_task_id, 
                    model_id=model_db_id, 
                    status=final_status,
                    ai_service_task_id=tripo_task_id
                )
                logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} status to '{final_status}'.")
            except Exception as db_update_e:
                logger.error(f"Celery task {celery_task_id}: CRITICAL - Failed to update DB {model_db_id} to '{final_status}': {db_update_e}", exc_info=True)
        
        if error_message:
            raise CeleryTaskException(error_message)

    # Synchronous wrapper
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(process_tripo_request())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: Final error state: {type(e).__name__} - {str(e)}", exc_info=True)
        raise

@celery_app.task(bind=True)
def generate_tripo_refine_model_task(self, model_db_id: str, model_bytes: bytes, original_filename: str, request_data_dict: dict):
    """Celery task to call Tripo AI refine-model and update DB."""
    client_task_id = request_data_dict.get("task_id")
    celery_task_id = self.request.id
    logger.info(f"Celery task {celery_task_id} for DB record {model_db_id} (Client Task ID: {client_task_id}): Starting Tripo AI refine-model.")
    
    async def process_tripo_request():
        final_status = "failed"
        tripo_task_id = None
        error_message = None
        
        try:
            request_data = RefineModelRequest(**request_data_dict)

            await supabase_handler.update_model_record(
                task_id=client_task_id, 
                model_id=model_db_id, 
                status="processing"
            )
            logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} status to 'processing'.")

            # Call Tripo AI with model bytes
            tripo_response = await tripo_client.refine_model(
                model_bytes=model_bytes,
                original_filename=original_filename,
                request_model=request_data
            )
            
            tripo_task_id = tripo_response.get("data", {}).get("task_id")
            if not tripo_task_id:
                error_message = "Tripo AI (refine-model) did not return a valid task ID."
                logger.error(f"Celery task {celery_task_id}: {error_message}")
                raise CeleryTaskException(error_message)

            logger.info(f"Celery task {celery_task_id}: Got Tripo AI task ID: {tripo_task_id}")

            await supabase_handler.update_model_record(
                task_id=client_task_id, 
                model_id=model_db_id, 
                ai_service_task_id=tripo_task_id, 
                status="processing"
            )

            # Wait for completion and get result - implement proper polling loop
            max_polls = 180  # 3 minutes with 1-second intervals
            poll_count = 0
            
            while poll_count < max_polls:
                tripo_response = await tripo_client.poll_tripo_task_status(tripo_task_id)
                normalized_result = tripo_client.normalize_tripo_status(tripo_response)
                
                task_status = normalized_result.get("status")
                progress = normalized_result.get("progress", 0)
                
                logger.info(f"Celery task {celery_task_id}: Tripo task {tripo_task_id} status: {task_status}, progress: {progress}%")
                
                if task_status == "complete":
                    result_url = normalized_result.get("result_url")
                    if not result_url:
                        error_message = "Tripo AI task complete but no result URL."
                        logger.error(f"Celery task {celery_task_id}: {error_message}")
                        raise CeleryTaskException(error_message)

                    # Download from Tripo's temporary URL
                    logger.info(f"Celery task {celery_task_id}: Downloading refined model from {result_url}")
                    async with httpx.AsyncClient() as http_client:
                        dl_response = await http_client.get(result_url, timeout=settings.TRIPO_DOWNLOAD_TIMEOUT_SECONDS)
                        dl_response.raise_for_status()
                        model_data_bytes = dl_response.content

                    # Upload to our Supabase
                    final_asset_url = await supabase_handler.upload_asset_to_storage(
                        task_id=client_task_id,
                        asset_type_plural=supabase_handler.get_asset_type_for_models(),
                        file_name="refined_model.glb",
                        asset_data=model_data_bytes,
                        content_type="model/gltf-binary"
                    )

                    # Update DB record with final URL and complete status
                    await supabase_handler.update_model_record(
                        task_id=client_task_id,
                        model_id=model_db_id,
                        asset_url=final_asset_url,
                        status="complete",
                        ai_service_task_id=tripo_task_id,
                        prompt=request_data.prompt
                    )

                    final_status = "complete"
                    logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} with refined model URL and status 'complete'.")
                    
                    return {
                        'status': final_status,
                        'result_url': final_asset_url,
                        'db_record_id': model_db_id,
                        'client_task_id': client_task_id,
                        'tripo_task_id': tripo_task_id
                    }
                elif task_status in ["failed", "cancelled", "unknown"]:
                    error_message = f"Tripo AI task failed with status: {task_status}"
                    logger.error(f"Celery task {celery_task_id}: {error_message}")
                    raise CeleryTaskException(error_message)
                
                # Task is still pending or processing, wait and poll again
                poll_count += 1
                await asyncio.sleep(1)
            
            # If we reach here, polling timed out
            error_message = f"Tripo AI task polling timed out after {max_polls} polls"
            logger.error(f"Celery task {celery_task_id}: {error_message}")
            raise CeleryTaskException(error_message)

        except httpx.HTTPStatusError as e_http:
            error_message = f"HTTP error during Tripo refine call: {e_http.response.status_code} - {getattr(e_http.response, 'text', 'No text')}"
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: {error_message}", exc_info=True)
            final_status = "failed"
        except CeleryTaskException as e_celery_task:
            error_message = str(e_celery_task)
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: CeleryTaskException: {error_message}", exc_info=True)
            final_status = "failed"
        except Exception as e_unhandled:
            error_message = f"Unexpected error: {type(e_unhandled).__name__} - {str(e_unhandled)}"
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: {error_message}", exc_info=True)
            final_status = "failed"

        if final_status != "complete":
            try:
                await supabase_handler.update_model_record(
                    task_id=client_task_id, 
                    model_id=model_db_id, 
                    status=final_status,
                    ai_service_task_id=tripo_task_id
                )
                logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} status to '{final_status}'.")
            except Exception as db_update_e:
                logger.error(f"Celery task {celery_task_id}: CRITICAL - Failed to update DB {model_db_id} to '{final_status}': {db_update_e}", exc_info=True)
        
        if error_message:
            raise CeleryTaskException(error_message)

    # Synchronous wrapper
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(process_tripo_request())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: Final error state: {type(e).__name__} - {str(e)}", exc_info=True)
        raise

# Stability AI Tasks

@celery_app.task(bind=True)
def generate_stability_image_task(self, concept_image_db_id: int, image_bytes: bytes, request_data_dict: dict, operation_type: str):
    """Celery task for Stability AI image operations (image-to-image, text-to-image, sketch-to-image)."""
    client_task_id = request_data_dict.get("task_id")
    celery_task_id = self.request.id
    logger.info(f"Celery task {celery_task_id} for DB record {concept_image_db_id} (Client Task ID: {client_task_id}): Starting Stability AI {operation_type}.")
    
    async def process_stability_request():
        final_status = "failed"
        error_message = None
        
        try:
            # Update DB record to 'processing'
            await supabase_handler.update_concept_image_record(
                task_id=client_task_id,
                concept_image_id=concept_image_db_id,
                status="processing"
            )
            logger.info(f"Celery task {celery_task_id}: Updated DB record {concept_image_db_id} status to 'processing'.")

            # Call appropriate Stability AI method based on operation type
            if operation_type == "image_to_image":
                request_data = ImageToImageRequest(**request_data_dict)
                result_bytes = await stability_client.image_to_image(
                    image_bytes=image_bytes,
                    prompt=request_data.prompt,
                    style_preset=request_data.style_preset,
                    fidelity=request_data.fidelity,
                    negative_prompt=request_data.negative_prompt,
                    output_format=request_data.output_format,
                    seed=request_data.seed
                )
            elif operation_type == "text_to_image":
                request_data = TextToImageRequest(**request_data_dict)
                result_bytes = await stability_client.text_to_image(
                    prompt=request_data.prompt,
                    style_preset=request_data.style_preset,
                    aspect_ratio=request_data.aspect_ratio,
                    negative_prompt=request_data.negative_prompt,
                    output_format=request_data.output_format,
                    seed=request_data.seed
                )
            elif operation_type == "sketch_to_image":
                request_data = SketchToImageRequest(**request_data_dict)
                result_bytes = await stability_client.sketch_to_image(
                    sketch_bytes=image_bytes,
                    prompt=request_data.prompt,
                    control_strength=request_data.control_strength,
                    style_preset=request_data.style_preset,
                    negative_prompt=request_data.negative_prompt,
                    output_format=request_data.output_format
                )
            elif operation_type == "remove_background":
                request_data = RemoveBackgroundRequest(**request_data_dict)
                result_bytes = await stability_client.remove_background(
                    image_bytes=image_bytes,
                    output_format=request_data.output_format
                )
            elif operation_type == "search_and_recolor":
                request_data = SearchAndRecolorRequest(**request_data_dict)
                result_bytes = await stability_client.search_and_recolor(
                    image_bytes=image_bytes,
                    prompt=request_data.prompt,
                    select_prompt=request_data.select_prompt,
                    negative_prompt=request_data.negative_prompt,
                    grow_mask=request_data.grow_mask,
                    seed=request_data.seed,
                    output_format=request_data.output_format,
                    style_preset=request_data.style_preset
                )
            else:
                error_message = f"Unknown Stability operation type: {operation_type}"
                logger.error(f"Celery task {celery_task_id}: {error_message}")
                raise CeleryTaskException(error_message)

            # Upload result to Supabase
            file_extension = request_data_dict.get("output_format", "png")
            file_name = f"stability_{operation_type}.{file_extension}"
            
            supabase_url = await supabase_handler.upload_asset_to_storage(
                task_id=client_task_id,
                asset_type_plural=supabase_handler.get_asset_type_for_concepts(),
                file_name=file_name,
                asset_data=result_bytes,
                content_type=f"image/{file_extension}"
            )
            
            # Update DB record with result
            await supabase_handler.update_concept_image_record(
                task_id=client_task_id,
                concept_image_id=concept_image_db_id,
                asset_url=supabase_url,
                status="complete",
                prompt=request_data_dict.get("prompt"),
                style=request_data_dict.get("style_preset")
            )
            
            final_status = "complete"
            logger.info(f"Celery task {celery_task_id}: Updated DB record {concept_image_db_id} with asset_url {supabase_url} and status 'complete'.")
            
            return {'status': final_status, 'asset_url': supabase_url, 'db_record_id': concept_image_db_id}

        except httpx.HTTPStatusError as e_http:
            error_message = f"HTTP error during Stability call: {e_http.response.status_code} - {getattr(e_http.response, 'text', 'No text')}"
            logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: {error_message}", exc_info=True)
            final_status = "failed"
        except CeleryTaskException as e_celery_task:
            error_message = str(e_celery_task)
            logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: CeleryTaskException: {error_message}", exc_info=True)
            final_status = "failed"
        except Exception as e_unhandled:
            error_message = f"Unexpected error: {type(e_unhandled).__name__} - {str(e_unhandled)}"
            logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: {error_message}", exc_info=True)
            final_status = "failed"

        # Update DB record with final status if failed
        if final_status != "complete":
            try:
                await supabase_handler.update_concept_image_record(
                    task_id=client_task_id,
                    concept_image_id=concept_image_db_id,
                    status=final_status
                )
                logger.info(f"Celery task {celery_task_id}: Updated DB record {concept_image_db_id} status to '{final_status}'.")
            except Exception as db_update_e:
                logger.error(f"Celery task {celery_task_id}: CRITICAL - Failed to update DB record {concept_image_db_id} to '{final_status}': {db_update_e}", exc_info=True)
        
        if error_message:
            raise CeleryTaskException(error_message)

    # Synchronous wrapper
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(process_stability_request())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: Final error state: {type(e).__name__} - {str(e)}", exc_info=True)
        raise

@celery_app.task(bind=True)
def generate_stability_model_task(self, model_db_id: str, image_bytes: bytes, request_data_dict: dict):
    """Celery task for Stability AI 3D model generation (image-to-model)."""
    client_task_id = request_data_dict.get("task_id")
    celery_task_id = self.request.id
    logger.info(f"Celery task {celery_task_id} for DB record {model_db_id} (Client Task ID: {client_task_id}): Starting Stability AI image-to-model.")
    
    async def process_stability_request():
        final_status = "failed"
        error_message = None
        
        try:
            request_data = ImageToModelRequest(**request_data_dict)
            
            # Update DB record to 'processing'
            await supabase_handler.update_model_record(
                task_id=client_task_id,
                model_id=model_db_id,
                status="processing"
            )
            logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} status to 'processing'.")

            # Call Stability AI SPAR3D
            result_bytes = await stability_client.image_to_model(
                image_bytes=image_bytes,
                texture_resolution=request_data.texture_resolution,
                remesh=request_data.remesh,
                foreground_ratio=request_data.foreground_ratio,
                target_type=request_data.target_type,
                target_count=request_data.target_count,
                guidance_scale=request_data.guidance_scale,
                seed=request_data.seed
            )

            # Upload result to Supabase
            supabase_url = await supabase_handler.upload_asset_to_storage(
                task_id=client_task_id,
                asset_type_plural=supabase_handler.get_asset_type_for_models(),
                file_name="stability_model.glb",
                asset_data=result_bytes,
                content_type="model/gltf-binary"
            )
            
            # Update DB record with result
            await supabase_handler.update_model_record(
                task_id=client_task_id,
                model_id=model_db_id,
                asset_url=supabase_url,
                status="complete",
                prompt=request_data.prompt
            )
            
            final_status = "complete"
            logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} with asset_url {supabase_url} and status 'complete'.")
            
            return {'status': final_status, 'asset_url': supabase_url, 'db_record_id': model_db_id}

        except httpx.HTTPStatusError as e_http:
            error_message = f"HTTP error during Stability call: {e_http.response.status_code} - {getattr(e_http.response, 'text', 'No text')}"
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: {error_message}", exc_info=True)
            final_status = "failed"
        except CeleryTaskException as e_celery_task:
            error_message = str(e_celery_task)
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: CeleryTaskException: {error_message}", exc_info=True)
            final_status = "failed"
        except Exception as e_unhandled:
            error_message = f"Unexpected error: {type(e_unhandled).__name__} - {str(e_unhandled)}"
            logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: {error_message}", exc_info=True)
            final_status = "failed"

        # Update DB record with final status if failed
        if final_status != "complete":
            try:
                await supabase_handler.update_model_record(
                    task_id=client_task_id,
                    model_id=model_db_id,
                    status=final_status
                )
                logger.info(f"Celery task {celery_task_id}: Updated DB record {model_db_id} status to '{final_status}'.")
            except Exception as db_update_e:
                logger.error(f"Celery task {celery_task_id}: CRITICAL - Failed to update DB record {model_db_id} to '{final_status}': {db_update_e}", exc_info=True)
        
        if error_message:
            raise CeleryTaskException(error_message)

    # Synchronous wrapper
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(process_stability_request())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Celery task {celery_task_id} for DB {model_db_id}: Final error state: {type(e).__name__} - {str(e)}", exc_info=True)
        raise

# Recraft AI Tasks

@celery_app.task(bind=True)
def generate_recraft_image_task(self, concept_image_db_id: int, image_bytes: bytes, request_data_dict: dict, operation_type: str):
    """Celery task for Recraft AI image operations (image-to-image, text-to-image, remove-background)."""
    client_task_id = request_data_dict.get("task_id")
    celery_task_id = self.request.id
    logger.info(f"Celery task {celery_task_id} for DB record {concept_image_db_id} (Client Task ID: {client_task_id}): Starting Recraft AI {operation_type}.")
    
    async def process_recraft_request():
        final_status = "failed"
        error_message = None
        
        try:
            # Update DB record to 'processing'
            await supabase_handler.update_concept_image_record(
                task_id=client_task_id,
                concept_image_id=concept_image_db_id,
                status="processing"
            )
            logger.info(f"Celery task {celery_task_id}: Updated DB record {concept_image_db_id} status to 'processing'.")

            # Call appropriate Recraft AI method based on operation type
            if operation_type == "image_to_image":
                request_data = ImageToImageRequest(**request_data_dict)
                image_urls = await recraft_client.image_to_image(
                    image_bytes=image_bytes,
                    prompt=request_data.prompt,
                    style=request_data.style,
                    substyle=request_data.substyle,
                    strength=request_data.strength,
                    negative_prompt=request_data.negative_prompt,
                    n=request_data.n,
                    model=request_data.model,
                    response_format=request_data.response_format,
                    style_id=request_data.style_id
                )
            elif operation_type == "text_to_image":
                request_data = TextToImageRequest(**request_data_dict)
                image_urls = await recraft_client.text_to_image(
                    prompt=request_data.prompt,
                    style=request_data.style,
                    substyle=request_data.substyle,
                    n=request_data.n,
                    model=request_data.model,
                    response_format=request_data.response_format,
                    size=request_data.size,
                    style_id=request_data.style_id
                )
            elif operation_type == "remove_background":
                request_data = RemoveBackgroundRequest(**request_data_dict)
                image_url = await recraft_client.remove_background(
                    image_bytes=image_bytes,
                    response_format=request_data.response_format
                )
                image_urls = [image_url]  # Convert single URL to list for consistent processing
            elif operation_type == "inpaint":
                request_data = ImageInpaintRequest(**request_data_dict)
                # Extract mask bytes from request data (passed from router)
                mask_bytes = request_data_dict.get("mask_bytes")
                if not mask_bytes:
                    error_message = "Mask bytes not found in request data for inpaint operation"
                    logger.error(f"Celery task {celery_task_id}: {error_message}")
                    raise CeleryTaskException(error_message)
                
                image_urls = await recraft_client.inpaint(
                    image_bytes=image_bytes,
                    mask_bytes=mask_bytes,
                    prompt=request_data.prompt,
                    negative_prompt=request_data.negative_prompt,
                    n=request_data.n,
                    style=request_data.style,
                    substyle=request_data.substyle,
                    model=request_data.model,
                    response_format=request_data.response_format,
                    style_id=request_data.style_id
                )
            else:
                error_message = f"Unknown Recraft operation type: {operation_type}"
                logger.error(f"Celery task {celery_task_id}: {error_message}")
                raise CeleryTaskException(error_message)

            if not image_urls:
                error_message = "Recraft AI did not return any image URLs."
                logger.error(f"Celery task {celery_task_id}: {error_message}")
                raise CeleryTaskException(error_message)

            # Download and upload the first image (primary result)
            first_image_url = image_urls[0]
            logger.info(f"Celery task {celery_task_id}: Downloading image from {first_image_url}")
            
            result_bytes = await recraft_client.download_image(first_image_url)
            
            # Upload result to Supabase
            file_name = f"recraft_{operation_type}.png"
            
            supabase_url = await supabase_handler.upload_asset_to_storage(
                task_id=client_task_id,
                asset_type_plural=supabase_handler.get_asset_type_for_concepts(),
                file_name=file_name,
                asset_data=result_bytes,
                content_type="image/png"
            )
            
            # Update DB record with result
            await supabase_handler.update_concept_image_record(
                task_id=client_task_id,
                concept_image_id=concept_image_db_id,
                asset_url=supabase_url,
                status="complete",
                prompt=request_data_dict.get("prompt"),
                style=request_data_dict.get("style")
            )
            
            final_status = "complete"
            logger.info(f"Celery task {celery_task_id}: Updated DB record {concept_image_db_id} with asset_url {supabase_url} and status 'complete'.")
            
            return {'status': final_status, 'asset_url': supabase_url, 'db_record_id': concept_image_db_id, 'all_image_urls': image_urls}

        except httpx.HTTPStatusError as e_http:
            error_message = f"HTTP error during Recraft call: {e_http.response.status_code} - {getattr(e_http.response, 'text', 'No text')}"
            logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: {error_message}", exc_info=True)
            final_status = "failed"
        except CeleryTaskException as e_celery_task:
            error_message = str(e_celery_task)
            logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: CeleryTaskException: {error_message}", exc_info=True)
            final_status = "failed"
        except Exception as e_unhandled:
            error_message = f"Unexpected error: {type(e_unhandled).__name__} - {str(e_unhandled)}"
            logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: {error_message}", exc_info=True)
            final_status = "failed"

        # Update DB record with final status if failed
        if final_status != "complete":
            try:
                await supabase_handler.update_concept_image_record(
                    task_id=client_task_id,
                    concept_image_id=concept_image_db_id,
                    status=final_status
                )
                logger.info(f"Celery task {celery_task_id}: Updated DB record {concept_image_db_id} status to '{final_status}'.")
            except Exception as db_update_e:
                logger.error(f"Celery task {celery_task_id}: CRITICAL - Failed to update DB record {concept_image_db_id} to '{final_status}': {db_update_e}", exc_info=True)
        
        if error_message:
            raise CeleryTaskException(error_message)

    # Synchronous wrapper
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(process_recraft_request())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Celery task {celery_task_id} for DB {concept_image_db_id}: Final error state: {type(e).__name__} - {str(e)}", exc_info=True)
        raise 