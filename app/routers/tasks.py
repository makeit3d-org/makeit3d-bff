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

@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status_endpoint(
    task_id: str, 
    tenant: Optional[TenantContext] = Depends(get_optional_tenant)
):
    """
    Polls the status of an asynchronous task (Celery task).
    Supports all providers: OpenAI, Stability, Recraft, Flux, TripoAI, and custom processing (downscale).
    
    The service type is automatically detected from the Celery task name/result.
    
    Authentication is optional - if provided, adds tenant context to logs.
    """
    tenant_info = f" from tenant: {tenant.tenant_id}" if tenant else " (no auth)"
    logger.info(f"Received status request for task ID: {task_id}, service hint: None{tenant_info}")

    celery_task_result = celery_app.AsyncResult(task_id)

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
        logger.error(f"Celery task {task_id} failed. Info: {error_info}")
        return TaskStatusResponse(task_id=task_id, status=task_status_to_return, error=error_info, asset_url=None)

    elif celery_task_result.successful():
        celery_payload = celery_task_result.result
        
        if not celery_payload or not isinstance(celery_payload, dict):
            logger.error(f"Celery task {task_id} complete but returned an invalid payload: {celery_payload}")
            return TaskStatusResponse(task_id=task_id, status="failed", error="Celery task result payload invalid.", asset_url=None)

        # Auto-detect service type from task name or result payload
        task_name = getattr(celery_task_result.task, 'name', None) if hasattr(celery_task_result, 'task') else None
        detected_service = None
        
        # Auto-detect from task name
        if task_name:
            if 'tripo' in task_name.lower():
                detected_service = 'tripoai'
            elif 'openai' in task_name.lower():
                detected_service = 'openai'
            elif 'stability' in task_name.lower():
                detected_service = 'stability'
            elif 'recraft' in task_name.lower():
                detected_service = 'recraft'
            elif 'flux' in task_name.lower():
                detected_service = 'flux'
            elif 'downscale' in task_name.lower():
                detected_service = 'downscale'
        
        # Auto-detect from result payload if task name detection failed
        if not detected_service and celery_payload:
            if celery_payload.get('tripo_task_id'):
                detected_service = 'tripoai'
            elif celery_payload.get('provider'):
                detected_service = celery_payload.get('provider')
            else:
                # Default fallback for synchronous tasks
                detected_service = 'synchronous'
        
        logger.info(f"Task {task_id}: detected service '{detected_service}' (task_name: {task_name})")

        db_record_id = celery_payload.get("db_record_id")
        client_task_id = celery_payload.get("client_task_id") 

        if detected_service == "tripoai":
            # Handle TripoAI (asynchronous polling required)
            tripo_provider_task_id = celery_payload.get("tripo_task_id")
            
            if not db_record_id or not tripo_provider_task_id or not client_task_id:
                logger.error(f"TripoAI Celery task {task_id} result missing key data. Payload: {celery_payload}")
                if db_record_id and client_task_id: # Try to update DB even if tripo_provider_task_id is missing
                    try: await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                    except Exception as e_upd: logger.error(f"Failed to update model {db_record_id} to failed: {e_upd}")
                return TaskStatusResponse(task_id=task_id, status="failed", error="TripoAI Celery task result incomplete.", asset_url=None)

            logger.info(f"Polling Tripo AI for their task ID: {tripo_provider_task_id} (Celery task: {task_id}, DB Record: {db_record_id}) ")
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
                            return TaskStatusResponse(task_id=task_id, status="failed", error="Model record not found in database")
                        
                        final_asset_url = model_record.get("asset_url")
                        
                        if not final_asset_url or final_asset_url == "pending":
                            logger.error(f"Tripo AI task {tripo_provider_task_id} (DB {db_record_id}) complete but no asset URL in database")
                            await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                            return TaskStatusResponse(task_id=task_id, status="failed", error="No asset URL found in database")

                        # Update the record status to complete
                        await supabase_handler.update_model_record(
                            task_id=client_task_id, 
                            model_id=db_record_id, 
                            status="complete", 
                            ai_service_task_id=tripo_provider_task_id
                        )
                        
                        logger.info(f"Tripo AI task {tripo_provider_task_id} (DB {db_record_id}): Using existing asset URL from database: {final_asset_url}")
                        return TaskStatusResponse(task_id=task_id, status="complete", asset_url=final_asset_url, progress=100)
                        
                    except Exception as e:
                        logger.error(f"Error fetching model record {db_record_id}: {e}")
                        await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                        return TaskStatusResponse(task_id=task_id, status="failed", error=f"Database error: {str(e)}")

                elif tripo_job_status == "failed":
                    tripo_error_info = tripo_data.get("error", "Tripo AI task failed without specific error.")
                    logger.error(f"Tripo AI task {tripo_provider_task_id} (DB {db_record_id}) failed. Error: {tripo_error_info}")
                    await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed", metadata={"tripo_error": tripo_error_info})
                    return TaskStatusResponse(task_id=task_id, status="failed", error=tripo_error_info, progress=tripo_progress)
                
                elif tripo_job_status in ["running", "queued"]:
                    logger.info(f"Tripo AI task {tripo_provider_task_id} (DB {db_record_id}) is still processing (status: {tripo_job_status}, progress: {tripo_progress}%).")
                    return TaskStatusResponse(task_id=task_id, status="processing", progress=tripo_progress)
                
                else: 
                    logger.warning(f"Tripo AI task {tripo_provider_task_id} (DB {db_record_id}) unknown status: {tripo_job_status}. Response: {tripo_status_response}")
                    await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                    return TaskStatusResponse(task_id=task_id, status="failed", error=f"Tripo unknown status: {tripo_job_status}", progress=tripo_progress)

            except httpx.HTTPStatusError as e_http_tripo:
                error_info = f"HTTP error polling Tripo status ({tripo_provider_task_id}): {e_http_tripo.response.status_code} - {e_http_tripo.response.text}"
                logger.error(f"{error_info} (DB {db_record_id})", exc_info=True)
                await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                return TaskStatusResponse(task_id=task_id, status="failed", error=error_info)
            except Exception as e_poll:
                error_info = f"Error polling/processing Tripo result for {tripo_provider_task_id}: {str(e_poll)}"
                logger.error(f"{error_info} (DB {db_record_id})", exc_info=True)
                try: await supabase_handler.update_model_record(task_id=client_task_id, model_id=db_record_id, status="failed")
                except Exception as e_db_upd: logger.error(f"Failed to update model {db_record_id} status after poll error: {e_db_upd}")
                return TaskStatusResponse(task_id=task_id, status="failed", error=error_info)
        
        elif detected_service in ["openai", "stability", "recraft", "flux", "downscale", "synchronous"]:
            # Handle synchronous providers (OpenAI, Stability, Recraft, Flux, Downscale)
            # These complete within the Celery task and return asset URLs directly
            
            task_reported_status = celery_payload.get("status", "complete")  # Default to complete for successful Celery tasks
            
            if task_reported_status == "complete":
                try:
                    if db_record_id is None:
                         logger.error(f"{detected_service.capitalize()} Celery task {task_id} result missing db_record_id.")
                         raise HTTPException(status_code=500, detail=f"{detected_service.capitalize()} task result incomplete for DB lookup.")

                    # Determine if this is an image or model record
                    is_model_task = detected_service == "stability" and celery_payload.get("operation_type") == "image_to_model"
                    
                    if is_model_task:
                        # Fetch model record
                        from supabase_handler import supabase_client
                        from config import settings
                        
                        def get_model_record():
                            response = supabase_client.table(settings.models_table_name).select("*").eq("id", db_record_id).execute()
                            return response.data[0] if response.data else None
                        
                        record = await run_in_threadpool(get_model_record)
                        record_type = "model"
                    else:
                        # Fetch image record
                        record = await supabase_handler.get_image_record_by_id(image_id=db_record_id)
                        record_type = "image"
                    
                    if not record:
                         logger.error(f"Failed to fetch {record_type} record for ID {db_record_id} (Celery task {task_id}).")
                         return TaskStatusResponse(task_id=task_id, status="failed", error=f"{record_type.capitalize()} record {db_record_id} not found.", asset_url=None)

                    final_asset_url = record.get("asset_url")
                    if not final_asset_url:
                        # Fallback to URLs from Celery result if main record URL is missing
                        url_keys = ["image_urls", "asset_urls", "model_urls", "asset_url"]
                        for key in url_keys:
                            if celery_payload.get(key):
                                if isinstance(celery_payload[key], list) and len(celery_payload[key]) > 0:
                                    final_asset_url = celery_payload[key][0]
                                    break
                                elif isinstance(celery_payload[key], str):
                                    final_asset_url = celery_payload[key]
                                    break
                        
                        if not final_asset_url:
                             logger.error(f"{detected_service.capitalize()} Celery task {task_id} (DB record {db_record_id}) complete but no asset URL found in DB or Celery payload.")
                             return TaskStatusResponse(task_id=task_id, status="failed", error="No asset URL found.", asset_url=None)
                        else:
                            logger.warning(f"{detected_service.capitalize()} Celery task {task_id} (DB record {db_record_id}): asset_url missing in DB, using from Celery payload: {final_asset_url}")
                    
                    logger.info(f"{detected_service.capitalize()} Celery task {task_id} (DB record {db_record_id}) complete. Asset URL: {final_asset_url}")
                    return TaskStatusResponse(task_id=task_id, status="complete", asset_url=final_asset_url, progress=100)

                except Exception as e_db_fetch:
                    logger.error(f"Error fetching/processing {detected_service} record {db_record_id} for Celery task {task_id}: {e_db_fetch}", exc_info=True)
                    return TaskStatusResponse(task_id=task_id, status="failed", error=str(e_db_fetch), asset_url=None)
            
            elif task_reported_status and "failed" in task_reported_status:
                logger.error(f"{detected_service.capitalize()} Celery task {task_id} (DB record {db_record_id}) reported failure: {task_reported_status}. Payload: {celery_payload}")
                return TaskStatusResponse(task_id=task_id, status="failed", error=f"{detected_service.capitalize()} task failed: {task_reported_status}", asset_url=None)
            else: 
                # Task still processing as per its own status, or unknown status
                current_status = "processing" if task_reported_status else "processing"
                logger.info(f"{detected_service.capitalize()} Celery task {task_id} (DB record {db_record_id}) current status from task payload: {current_status}")
                return TaskStatusResponse(task_id=task_id, status=current_status, asset_url=None)
        
        else: 
            logger.error(f"Unknown/unsupported service for task ID {task_id}: {detected_service}")
            return TaskStatusResponse(task_id=task_id, status="failed", error=f"Unsupported service: {detected_service}", asset_url=None)
    
    else: # PENDING, RETRY, STARTED, etc.
        # Handle pending/processing tasks
        logger.info(f"Celery task {task_id} status: {task_status_from_celery}")
        
        # For TripoAI tasks, always try to get progress from Tripo API regardless of Celery status
        try:
            # Try to get the Celery task result to extract info (even if Celery is pending)
            celery_payload = celery_task_result.result
            if celery_payload and isinstance(celery_payload, dict):
                # Auto-detect service type
                task_name = getattr(celery_task_result.task, 'name', None) if hasattr(celery_task_result, 'task') else None
                detected_service = service  # Use provided service hint if available
                
                if not detected_service:
                    # Auto-detect from task name
                    if task_name:
                        if 'tripo' in task_name.lower():
                            detected_service = 'tripoai'
                        elif 'openai' in task_name.lower():
                            detected_service = 'openai'
                        elif 'stability' in task_name.lower():
                            detected_service = 'stability'
                        elif 'recraft' in task_name.lower():
                            detected_service = 'recraft'
                        elif 'flux' in task_name.lower():
                            detected_service = 'flux'
                        elif 'downscale' in task_name.lower():
                            detected_service = 'downscale'
                    
                    # Auto-detect from result payload if task name detection failed
                    if not detected_service and celery_payload:
                        if celery_payload.get('tripo_task_id'):
                            detected_service = 'tripoai'
                        elif celery_payload.get('provider'):
                            detected_service = celery_payload.get('provider')
                        else:
                            # Default fallback for synchronous tasks
                            detected_service = 'synchronous'
                
                logger.info(f"Pending task {task_id}: detected service '{detected_service}' (task_name: {task_name})")
                
                # For TripoAI, try to get real progress from Tripo API
                if detected_service == 'tripoai':
                    tripo_provider_task_id = celery_payload.get("tripo_task_id")
                    db_record_id = celery_payload.get("db_record_id")
                    client_task_id = celery_payload.get("client_task_id")
                    
                    if tripo_provider_task_id:
                        logger.info(f"Celery task {task_id} status: {task_status_from_celery}, polling Tripo task {tripo_provider_task_id} for progress")
                        
                        # Poll Tripo for current status and progress
                        tripo_status_response = await tripo_client.poll_tripo_task_status(tripo_provider_task_id)
                        tripo_data = tripo_status_response.get("data", {})
                        tripo_job_status = tripo_data.get("status")
                        tripo_progress = tripo_data.get("progress", 0)
                        
                        logger.info(f"Tripo task {tripo_provider_task_id} status: {tripo_job_status}, progress: {tripo_progress}%")
                        
                        # Return processing status with real Tripo progress
                        return TaskStatusResponse(task_id=task_id, status="processing", progress=tripo_progress)
                        
        except Exception as e:
            logger.warning(f"Could not get enhanced progress for Celery task {task_id}: {e}")
            # Fall back to default behavior
        
        # Map Celery statuses to our simplified system (fallback)
        celery_status_mapping = {
            "PENDING": "pending",
            "STARTED": "processing", 
            "RETRY": "processing",
            "RECEIVED": "pending"
        }
        mapped_status = celery_status_mapping.get(task_status_from_celery, "processing")
        logger.info(f"Celery task {task_id} status from Celery: {task_status_from_celery} -> {mapped_status}")
        return TaskStatusResponse(task_id=task_id, status=mapped_status, asset_url=None) 