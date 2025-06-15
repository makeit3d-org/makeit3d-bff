import logging
from fastapi import APIRouter, HTTPException, Query, Depends
from celery_worker import celery_app # To get AsyncResult
from schemas.generation_schemas import TaskStatusResponse # Define or reuse an appropriate response schema
import supabase_handler
from ai_clients import tripo_client
from config import settings
import httpx
import base64 # For OpenAI, though asset is already stored by task. For Tripo, to decode if needed.
from concurrent.futures import ThreadPoolExecutor
from fastapi.concurrency import run_in_threadpool

# Import optional authentication
from auth import get_optional_tenant, TenantContext
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/{celery_task_id}/status", response_model=TaskStatusResponse)
async def get_task_status_endpoint(
    celery_task_id: str, 
    service: str = Query(..., description="The AI service used for the task: 'openai' or 'tripoai'"),
    tenant: Optional[TenantContext] = Depends(get_optional_tenant)
):
    """
    Polls the status of an asynchronous task (Celery task).
    For OpenAI, it primarily checks the Celery task result which contains direct Supabase URLs.
    For TripoAI, it checks the Celery task result for the Tripo AI task ID, then polls Tripo AI.
    If Tripo AI task is complete, it downloads the asset, uploads to app's Supabase,
    updates the DB record, and returns the final Supabase URL.
    
    Authentication is optional - if provided, adds tenant context to logs.
    """
    tenant_info = f" from tenant: {tenant.tenant_id}" if tenant else " (no auth)"
    logger.info(f"Received status request for Celery task ID: {celery_task_id}, service: {service}{tenant_info}")

    celery_task_result = celery_app.AsyncResult(celery_task_id)

    if not celery_task_result: # This check might always be true as AsyncResult creates an object.
        # More robust is to check celery_task_result.backend if it implies connection or existence.
        # For now, proceed assuming task_id is valid for Celery.
        pass 

    task_status_from_celery = celery_task_result.status
    error_info = None
    final_asset_url = None # This will be the Supabase URL

    if celery_task_result.failed():
        task_status_to_return = "failed" # Normalize status
        error_info = str(celery_task_result.info) if celery_task_result.info else "Celery task failed without specific error info."
        logger.error(f"Celery task {celery_task_id} failed. Info: {error_info}")
        return TaskStatusResponse(task_id=celery_task_id, status=task_status_to_return, error=error_info, asset_url=None)

    elif celery_task_result.successful():
        celery_payload = celery_task_result.result
        
        if not celery_payload or not isinstance(celery_payload, dict):
            logger.error(f"Celery task {celery_task_id} (service: {service}) complete but returned an invalid payload: {celery_payload}")
            return TaskStatusResponse(task_id=celery_task_id, status="failed", error="Celery task result payload invalid.", asset_url=None)

        db_record_id = celery_payload.get("db_record_id")
        # client_task_id is the main ID from the client, used for Supabase paths.
        # For OpenAI, it was part of the original request_data_dict.
        # For Tripo, the Celery task should also include it in its return payload.
        client_task_id = celery_payload.get("client_task_id") 

        if service == "openai":
            openai_task_reported_status = celery_payload.get("status") # Status reported by the OpenAI Celery task
            
            if openai_task_reported_status == "complete":
                try:
                    if db_record_id is None:
                         logger.error(f"OpenAI Celery task {celery_task_id} result missing db_record_id.")
                         raise HTTPException(status_code=500, detail="OpenAI task result incomplete for DB lookup.")

                    # Fetch the record from images using the correct supabase_handler function
                    image_record = await supabase_handler.get_image_record_by_id(image_id=db_record_id)
                    
                    if not image_record:
                         logger.error(f"Failed to fetch image record for ID {db_record_id} (Celery task {celery_task_id}).")
                         return TaskStatusResponse(task_id=celery_task_id, status="failed", error=f"Image record {db_record_id} not found.", asset_url=None)

                    final_asset_url = image_record.get("asset_url")
                    if not final_asset_url:
                        # Fallback to first URL from Celery result if main record URL is missing (e.g. n > 1 images)
                        if celery_payload.get("image_urls") and len(celery_payload["image_urls"]) > 0:
                            final_asset_url = celery_payload["image_urls"][0]
                            logger.warning(f"OpenAI Celery task {celery_task_id} (DB record {db_record_id}): asset_url missing in DB, using first from Celery payload: {final_asset_url}")
                        else:
                             logger.error(f"OpenAI Celery task {celery_task_id} (DB record {db_record_id}) complete but no asset URL found in DB or Celery payload.")
                             return TaskStatusResponse(task_id=celery_task_id, status="failed", error="No asset URL found.", asset_url=None)
                    
                    logger.info(f"OpenAI Celery task {celery_task_id} (DB record {db_record_id}) complete. Asset URL: {final_asset_url}")
                    return TaskStatusResponse(task_id=celery_task_id, status="complete", asset_url=final_asset_url)

                except Exception as e_db_fetch:
                    logger.error(f"Error fetching/processing OpenAI image record {db_record_id} for Celery task {celery_task_id}: {e_db_fetch}", exc_info=True)
                    return TaskStatusResponse(task_id=celery_task_id, status="failed", error=str(e_db_fetch), asset_url=None)
            
            elif openai_task_reported_status and "failed" in openai_task_reported_status:
                logger.error(f"OpenAI Celery task {celery_task_id} (DB record {db_record_id}) reported failure: {openai_task_reported_status}. Payload: {celery_payload}")
                return TaskStatusResponse(task_id=celery_task_id, status="failed", error=f"OpenAI task failed: {openai_task_reported_status}", asset_url=None)
            else: # Task still processing as per its own status, or unknown status
                current_openai_status = "processing" if openai_task_reported_status else "processing"
                logger.info(f"OpenAI Celery task {celery_task_id} (DB record {db_record_id}) current status from task payload: {current_openai_status}")
                return TaskStatusResponse(task_id=celery_task_id, status=current_openai_status, asset_url=None)

        elif service == "tripoai":
            tripo_provider_task_id = celery_payload.get("tripo_task_id")
            
            if not db_record_id or not tripo_provider_task_id or not client_task_id:
                logger.error(f"TripoAI Celery task {celery_task_id} result missing key data. Payload: {celery_payload}")
                if db_record_id and client_task_id: # Try to update DB even if tripo_provider_task_id is missing
                    try: await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                    except Exception as e_upd: logger.error(f"Failed to update model {db_record_id} to failed: {e_upd}")
                return TaskStatusResponse(task_id=celery_task_id, status="failed", error="TripoAI Celery task result incomplete.", asset_url=None)

            logger.info(f"Polling Tripo AI for their task ID: {tripo_provider_task_id} (Celery task: {celery_task_id}, DB Record: {db_record_id}) ")
            try:
                tripo_status_response = await tripo_client.poll_tripo_task_status(tripo_provider_task_id)
                tripo_data = tripo_status_response.get("data", {})
                tripo_job_status = tripo_data.get("status")
                tripo_progress = tripo_data.get("progress", 0)  # Extract progress field
                
                logger.info(f"Tripo AI task {tripo_provider_task_id} status from API: {tripo_job_status}, progress: {tripo_progress}%")

                if tripo_job_status == "success":
                    outputs = tripo_data.get("output", {})
                    # The Celery task should have already uploaded the model, so we just need to 
                    # fetch the final asset URL from the database record
                    
                    try:
                        # Get the model record from database which should have the final asset URL
                        from supabase_handler import supabase_client
                        from config import settings
                        
                        def get_model_record():
                            response = supabase_client.table(settings.models_table_name).select("*").eq("id", db_record_id).execute()
                            return response.data[0] if response.data else None
                        
                        model_record = await run_in_threadpool(get_model_record)
                        
                        if not model_record:
                            logger.error(f"Tripo AI task {tripo_provider_task_id} (DB {db_record_id}) complete but model record not found")
                            await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                            return TaskStatusResponse(task_id=celery_task_id, status="failed", error="Model record not found in database")
                        
                        final_asset_url = model_record.get("asset_url")
                        
                        if not final_asset_url or final_asset_url == "pending":
                            logger.error(f"Tripo AI task {tripo_provider_task_id} (DB {db_record_id}) complete but no asset URL in database")
                            await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                            return TaskStatusResponse(task_id=celery_task_id, status="failed", error="No asset URL found in database")

                        # Update the record status to complete
                        await supabase_handler.update_model_record(
                            task_id=client_task_id, 
                            model_id=db_record_id, 
                            status="complete", 
                            ai_service_task_id=tripo_provider_task_id
                        )
                        
                        logger.info(f"Tripo AI task {tripo_provider_task_id} (DB {db_record_id}): Using existing asset URL from database: {final_asset_url}")
                        return TaskStatusResponse(task_id=celery_task_id, status="complete", asset_url=final_asset_url, progress=100)
                        
                    except Exception as e:
                        logger.error(f"Error fetching model record {db_record_id}: {e}")
                        await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                        return TaskStatusResponse(task_id=celery_task_id, status="failed", error=f"Database error: {str(e)}")

                elif tripo_job_status == "failed":
                    tripo_error_info = tripo_data.get("error", "Tripo AI task failed without specific error.")
                    logger.error(f"Tripo AI task {tripo_provider_task_id} (DB {db_record_id}) failed. Error: {tripo_error_info}")
                    await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed", metadata={"tripo_error": tripo_error_info})
                    return TaskStatusResponse(task_id=celery_task_id, status="failed", error=tripo_error_info, progress=tripo_progress)
                
                elif tripo_job_status in ["running", "queued"]:
                    logger.info(f"Tripo AI task {tripo_provider_task_id} (DB {db_record_id}) is still processing (status: {tripo_job_status}, progress: {tripo_progress}%).")
                    return TaskStatusResponse(task_id=celery_task_id, status="processing", progress=tripo_progress)
                
                else: 
                    logger.warning(f"Tripo AI task {tripo_provider_task_id} (DB {db_record_id}) unknown status: {tripo_job_status}. Response: {tripo_status_response}")
                    await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                    return TaskStatusResponse(task_id=celery_task_id, status="failed", error=f"Tripo unknown status: {tripo_job_status}", progress=tripo_progress)

            except httpx.HTTPStatusError as e_http_tripo:
                error_info = f"HTTP error polling Tripo status ({tripo_provider_task_id}): {e_http_tripo.response.status_code} - {e_http_tripo.response.text}"
                logger.error(f"{error_info} (DB {db_record_id})", exc_info=True)
                await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                return TaskStatusResponse(task_id=celery_task_id, status="failed", error=error_info)
            except Exception as e_poll:
                error_info = f"Error polling/processing Tripo result for {tripo_provider_task_id}: {str(e_poll)}"
                logger.error(f"{error_info} (DB {db_record_id})", exc_info=True)
                try: await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                except Exception as e_db_upd: logger.error(f"Failed to update model {db_record_id} status after poll error: {e_db_upd}")
                return TaskStatusResponse(task_id=celery_task_id, status="failed", error=error_info)
        
        else: 
            logger.error(f"Unknown service for task ID {celery_task_id}: {service}")
            raise HTTPException(status_code=400, detail=f"Invalid service: {service}. Must be 'openai' or 'tripoai'.")

    else: # PENDING, RETRY, STARTED, etc.
        # For TripoAI tasks, always try to get progress from Tripo API regardless of Celery status
        if service == "tripoai":
            try:
                # Try to get the Celery task result to extract Tripo task ID (even if Celery is pending)
                celery_payload = celery_task_result.result
                if celery_payload and isinstance(celery_payload, dict):
                    tripo_provider_task_id = celery_payload.get("tripo_task_id")
                    db_record_id = celery_payload.get("db_record_id")
                    client_task_id = celery_payload.get("client_task_id")
                    
                    if tripo_provider_task_id:
                        logger.info(f"Celery task {celery_task_id} status: {task_status_from_celery}, polling Tripo task {tripo_provider_task_id} for progress")
                        
                        # Poll Tripo for current status and progress
                        tripo_status_response = await tripo_client.poll_tripo_task_status(tripo_provider_task_id)
                        
                        # Log the full Tripo response for debugging
                        logger.info(f"Full Tripo API response for task {tripo_provider_task_id}: {tripo_status_response}")
                        
                        tripo_data = tripo_status_response.get("data", {})
                        tripo_job_status = tripo_data.get("status")
                        tripo_progress = tripo_data.get("progress", 0)
                        
                        # Log the Tripo output URLs if available
                        output = tripo_data.get("output", {})
                        if output:
                            logger.info(f"Tripo task {tripo_provider_task_id} output URLs available:")
                            if output.get("model"):
                                logger.info(f"  - model: {output['model']}")
                            if output.get("base_model"):
                                logger.info(f"  - base_model: {output['base_model']}")
                            if output.get("pbr_model"):
                                logger.info(f"  - pbr_model: {output['pbr_model']}")
                            if output.get("rendered_image"):
                                logger.info(f"  - rendered_image: {output['rendered_image']}")
                        
                        logger.info(f"Tripo task {tripo_provider_task_id} status: {tripo_job_status}, progress: {tripo_progress}%")
                        
                        # Return processing status with real Tripo progress
                        return TaskStatusResponse(task_id=celery_task_id, status="processing", progress=tripo_progress)
                        
            except Exception as e:
                logger.warning(f"Could not get Tripo progress for Celery task {celery_task_id}: {e}")
                # Fall back to default behavior
        
        # Map Celery statuses to our simplified system (fallback)
        celery_status_mapping = {
            "PENDING": "pending",
            "STARTED": "processing", 
            "RETRY": "processing",
            "RECEIVED": "pending"
        }
        mapped_status = celery_status_mapping.get(task_status_from_celery, "processing")
        logger.info(f"Celery task {celery_task_id} (service: {service}) status from Celery: {task_status_from_celery} -> {mapped_status}")
        return TaskStatusResponse(task_id=celery_task_id, status=mapped_status, asset_url=None) 