import logging
import asyncio
import httpx
from typing import Dict, Any, List

from celery_worker import celery_app
from ai_clients import tripo_client
from ai_clients.stability_client import stability_client
from schemas.generation_schemas import (
    TextToModelRequest,
    ImageToModelRequest,
    RefineModelRequest
)
from config import settings
import supabase_handler

logger = logging.getLogger(__name__)

# Custom exception for Celery tasks to ensure serializable errors
class CeleryTaskException(Exception):
    pass

# Tripo AI Model Tasks

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

# Stability AI Model Tasks

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