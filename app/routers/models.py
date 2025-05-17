from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any
import httpx
import logging

from ..schemas.generation_schemas import TaskStatusResponse, ErrorResponse
from ..ai_clients import tripo_client, openai_client # Import both clients

logger = logging.getLogger(__name__)

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

    try:
        if service.lower() == 'tripo':
            tripo_response = await tripo_client.poll_tripo_task_status(task_id)
            # Normalize the Tripo response
            normalized_status = tripo_client.normalize_tripo_status(tripo_response)
            logger.info(f"Returning normalized status for Tripo task {task_id}: {normalized_status['status']}")
            return normalized_status

        elif service.lower() == 'openai':
            # As noted, OpenAI image generation is typically synchronous.
            # Simulate completed status for MVP.
            logger.info(f"Simulating completed status for OpenAI task {task_id} (OpenAI image generation is typically synchronous).")
            return TaskStatusResponse(status="completed", progress=100.0, result_url=None)

    except httpx.HTTPStatusError as e:
        # Handle specific HTTP errors from AI services
        if e.response.status_code == 404:
            logger.warning(f"Task with ID {task_id} not found for service {service}: {e.response.text}", exc_info=True)
            raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found for service {service}.")
        logger.error(f"HTTP error polling status for task ID {task_id} from service {service}: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(status_code=e.response.status_code, detail=f"{service.capitalize()} API error: {e.response.text}")
    except Exception as e:
        logger.error(f"Internal server error polling status for task ID {task_id} from service {service}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error while fetching task status: {e}") 