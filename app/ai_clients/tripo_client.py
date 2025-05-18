import httpx
from typing import Dict, Any, List, Optional
import logging

from app.config import settings
from app.schemas.generation_schemas import (
    TextToModelRequest,
    ImageToModelRequest,
    SketchToModelRequest,
    RefineModelRequest,
    SelectConceptRequest
)

logger = logging.getLogger(__name__)

TRIPO_API_BASE_URL_V1 = "https://api.tripo3d.ai/v1"
TRIPO_API_BASE_URL_V2 = "https://api.tripo3d.ai/v2"

async def call_tripo_task_api(task_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Generic function to call the Tripo AI /v2/openapi/task endpoint."""
    url = f"{TRIPO_API_BASE_URL_V2}/openapi/task"
    headers = {
        "Authorization": f"Bearer {settings.tripo_api_key}",
        "Content-Type": "application/json"
    }
    data = {"type": task_type, **payload}

    logger.info(f"Calling Tripo AI Task API ({task_type}): {url}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            logger.info(f"Tripo AI Task API response status: {response.status_code}")
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Tripo AI HTTP error ({task_type}): {e.response.status_code} - {e.response.text}", exc_info=True)
        raise # Re-raise the exception after logging
    except Exception as e:
        logger.error(f"Error calling Tripo AI Task API ({task_type}): {e}", exc_info=True)
        raise # Re-raise the exception after logging

async def generate_text_to_model(request_data: TextToModelRequest) -> Dict[str, Any]:
    """Calls Tripo AI text-to-model endpoint."""
    payload = request_data.model_dump()
    logger.info("Generating text-to-model with Tripo AI")
    return await call_tripo_task_api("text_to_model", payload)

async def generate_image_to_model(request_data: ImageToModelRequest) -> Dict[str, Any]:
    """Calls Tripo AI multiview-to-model endpoint."""
    payload = request_data.model_dump()
    logger.info("Generating image-to-model (multiview) with Tripo AI")
    return await call_tripo_task_api("multiview_to_model", payload)

async def generate_sketch_to_model(request_data: SketchToModelRequest) -> Dict[str, Any]:
    """Calls Tripo AI image-to-model endpoint."""
    payload = request_data.model_dump()
    logger.info("Generating sketch-to-model with Tripo AI")
    return await call_tripo_task_api("image_to_model", payload)

async def refine_model(request_data: RefineModelRequest) -> Dict[str, Any]:
    """Calls Tripo AI refine-model endpoint."""
    payload = request_data.model_dump()
    logger.info("Refining model with Tripo AI")
    return await call_tripo_task_api("refine_model", payload)

async def poll_tripo_task_status(task_id: str) -> Dict[str, Any]:
    """Polls Tripo AI for the status of a task."""
    url = f"{TRIPO_API_BASE_URL_V1}/task/{task_id}"
    headers = {
        "Authorization": f"Bearer {settings.tripo_api_key}"
    }

    logger.info(f"Polling Tripo AI task status for ID: {task_id}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            logger.info(f"Tripo AI status response status for ID {task_id}: {response.status_code}")
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Tripo AI HTTP error polling status for ID {task_id}: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise # Re-raise the exception after logging
    except Exception as e:
        logger.error(f"Error polling Tripo AI status for ID {task_id}: {e}", exc_info=True)
        raise # Re-raise the exception after logging

# Helper to normalize Tripo status response
def normalize_tripo_status(tripo_response: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes Tripo status response to a common format."""
    data = tripo_response.get("data", {})
    task_status = data.get("task_status")
    progress = data.get("progress")
    model_url = data.get("model_url") # Temporary URL

    # Map Tripo statuses to our internal simplified statuses
    status_map = {
        "pending": "pending",
        "running": "processing",
        "success": "completed",
        "failed": "failed",
        "cancelled": "failed", # Or a separate cancelled status if needed
    }

    normalized_status = {
        "status": status_map.get(task_status, "unknown"),
        "progress": progress,
        "result_url": model_url if task_status == "success" else None,
    }
    logger.debug(f"Normalized Tripo status for task ID {data.get('task_id')}: {normalized_status}")
    return normalized_status 