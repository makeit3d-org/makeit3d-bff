from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
import httpx
import logging
# import uuid # Removed
# import asyncio # Removed
from celery.result import AsyncResult # Import AsyncResult

from ..schemas.generation_schemas import TaskStatusResponse, ErrorResponse
from ..ai_clients import tripo_client#, openai_client # Keep tripo_client for polling
from app.celery_worker import celery_app # Import celery_app

logger = logging.getLogger(__name__)

# Removed in-memory task_store
# task_store: Dict[str, Dict[str, Any]] = {}

router = APIRouter()

@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse, responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def get_task_status(
    task_id: str,
    service: str = Query(..., description="Service that generated the task: 'openai' or 'tripo'")
):
    """Retrieves the status of a specific generation task from the relevant service."""
    logger.info(f"Received status request for task ID: {task_id} from service: {service}")
    if service.lower() not in ['openai', 'tripo']:
        logger.warning(f"Invalid 'service' query parameter: {service}")
        raise HTTPException(status_code=400, detail="Invalid 'service' query parameter. Must be 'openai' or 'tripo'.")

    # Get task from Celery backend
    task = AsyncResult(task_id, app=celery_app)

    # Map Celery states to simplified statuses
    status_map = {
        'PENDING': 'pending',
        'STARTED': 'processing',
        'RECEIVED': 'processing', # Tasks that are received by a worker
        'RETRY': 'processing', # Tasks that are being retried
        'PROGESS': 'processing', # Tasks that report intermediate progress
        'SUCCESS': 'completed',
        'FAILURE': 'failed',
        'REVOKED': 'failed', # Tasks that were revoked
    }

    celery_status = task.state
    normalized_status = status_map.get(celery_status, 'unknown')

    logger.info(f"Celery task {task_id} state: {celery_status} -> Normalized status: {normalized_status}")

    # Handle based on service and task state
    try:
        if service.lower() == 'tripo':
            if celery_status == 'SUCCESS':
                # Celery result for Tripo task is the Tripo task ID
                tripo_task_id = task.result.get('tripo_task_id')
                if not tripo_task_id:
                     logger.error(f"Celery task {task_id} succeeded but missing tripo_task_id in result: {task.result}")
                     raise HTTPException(status_code=500, detail="Internal server error: Missing Tripo task ID in result.")

                # Poll the actual Tripo API for the final status and result URL
                tripo_response = await tripo_client.poll_tripo_task_status(tripo_task_id)
                # Normalize the Tripo response
                normalized_tripo_status = tripo_client.normalize_tripo_status(tripo_response)
                logger.info(f"Returning normalized status for Tripo task {tripo_task_id} from Tripo API: {normalized_tripo_status['status']}")
                return TaskStatusResponse(
                    status=normalized_tripo_status['status'],
                    progress=normalized_tripo_status.get('progress'),
                    result_url=normalized_tripo_status.get('result_url'),
                    result=None # Tripo result is the model URL, returned as result_url
                )
            elif celery_status == 'FAILURE' or celery_status == 'REVOKED':
                 # Celery task failed, report failure
                 logger.error(f"Celery Tripo task {task_id} failed. Exception: {task.result}")
                 return TaskStatusResponse(status='failed', progress=0.0, result_url=None, result={'error': str(task.result)})
            else:
                # Celery task is pending or processing, return current state
                return TaskStatusResponse(
                    status=normalized_status,
                    progress=0.0, # We don't have Tripo progress until polling their API
                    result_url=None,
                    result=None
                )

        elif service.lower() == 'openai':
            if celery_status == 'SUCCESS':
                # Celery result for OpenAI task is the image data dictionary
                image_data_result = task.result
                if not isinstance(image_data_result, dict) or 'image_data' not in image_data_result:
                     logger.error(f"Celery task {task_id} succeeded but missing expected image_data in result: {task.result}")
                     raise HTTPException(status_code=500, detail="Internal server error: Missing image data in result.")

                logger.info(f"Returning completed status for OpenAI task {task_id} from Celery result.")
                return TaskStatusResponse(
                    status='completed',
                    progress=100.0,
                    result_url=None, # result_url is not applicable for OpenAI concepts
                    result=image_data_result # This contains {'image_data': [...]} 
                )
            elif celery_status == 'FAILURE' or celery_status == 'REVOKED':
                 # Celery task failed, report failure
                 logger.error(f"Celery OpenAI task {task_id} failed. Exception: {task.result}")
                 return TaskStatusResponse(status='failed', progress=0.0, result_url=None, result={'error': str(task.result)})
            else:
                 # Celery task is pending or processing, return current state
                return TaskStatusResponse(
                    status=normalized_status,
                    progress=0.0, # We don't have intermediate progress for OpenAI image gen via this method
                    result_url=None,
                    result=None
                )

    except Exception as e:
        logger.error(f"Internal server error polling Celery task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error while fetching task status: {e}") 