import httpx
from typing import Dict, Any, List, Optional
import logging
import json

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
    """Generic function to call the Tripo AI /v2/openapi/task endpoint according to V2 API docs."""
    url = f"{TRIPO_API_BASE_URL_V2}/openapi/task"
    headers = {
        "Authorization": f"Bearer {settings.tripo_api_key}",
        "Content-Type": "application/json"
    }
    
    # Prepare the request data according to V2 API docs
    request_data = {
        "type": task_type,
        **payload
    }
    
    logger.info(f"Calling Tripo AI Task API ({task_type}): {url}")
    logger.info(f"Request payload keys: {list(payload.keys())}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=request_data, headers=headers)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            
            response_data = response.json()
            logger.info(f"Tripo AI Task API response: {response_data}")
            
            # V2 API response structure: {"code": 0, "data": {"task_id": "..."}}
            if "code" not in response_data or response_data.get("code") != 0:
                logger.error(f"Unexpected response code from Tripo API: {response_data.get('code')}")
                raise ValueError(f"Tripo API returned non-zero code: {response_data}")
                
            # Extract task_id from the response
            if "data" not in response_data or "task_id" not in response_data.get("data", {}):
                logger.error(f"Missing task_id in Tripo API response: {response_data}")
                raise ValueError(f"Tripo API response missing task_id: {response_data}")
                
            logger.info(f"Successfully created Tripo task: {response_data['data']['task_id']}")
            return response_data
    except httpx.HTTPStatusError as e:
        logger.error(f"Tripo AI HTTP error ({task_type}): {e.response.status_code} - {e.response.text}", exc_info=True)
        raise # Re-raise the exception after logging
    except Exception as e:
        logger.error(f"Error calling Tripo AI Task API ({task_type}): {e}", exc_info=True)
        raise # Re-raise the exception after logging

async def generate_text_to_model(request_data: TextToModelRequest) -> Dict[str, Any]:
    """Calls Tripo AI text-to-model endpoint.
    
    According to V2 API docs:
    - type: text_to_model
    - prompt: Text input
    - texture: boolean (optional)
    - Additional optional parameters
    
    NOTE: The Tripo API appears to ignore the texture parameter and always use textures.
    """
    payload = request_data.model_dump(exclude_none=True) # exclude_none to avoid sending None values
    logger.info("Generating text-to-model with Tripo AI")
    logger.info(f"Text-to-model prompt: {payload.get('prompt', 'No prompt provided')}")

    # If style is an empty string, remove it from the payload
    if payload.get('style') == "":
        logger.info("Empty string provided for style, removing from payload for text_to_model")
        payload.pop('style')
    
    return await call_tripo_task_api("text_to_model", payload)

async def generate_image_to_model(request_data: ImageToModelRequest) -> Dict[str, Any]:
    """Calls Tripo AI multiview-to-model endpoint.
    
    According to V2 API docs:
    - type: multiview_to_model (for multiple images)
    - files: List of file info (front, left, back, right)
    - texture: boolean (optional)
    - Additional optional parameters
    
    NOTE: The Tripo API appears to ignore the texture parameter and always use textures.
    """
    payload = request_data.model_dump(exclude_none=True) # exclude_none to avoid sending None values
    logger.info("Generating image-to-model (multiview) with Tripo AI")
    
    # Special handling for multiple images - wrap in 'files' parameter for multiview API
    if "image_urls" in payload and isinstance(payload["image_urls"], list):
        image_urls = payload.pop("image_urls", [])
        
        # If only one image is provided, use image_to_model instead of multiview
        if len(image_urls) == 1:
            logger.info("Single image provided, using image_to_model API")
            
            # Create a payload for image_to_model
            image_model_payload = {
                "file": {"url": image_urls[0], "type": "jpg"}  # Assuming jpg, consider making type dynamic
            }
            
            # Copy key parameters from the original request
            if "prompt" in payload and payload["prompt"]:
                image_model_payload["prompt"] = payload["prompt"]
                
            if "texture" in payload:
                image_model_payload["texture"] = payload["texture"]
                
            # Remove empty style if present, otherwise copy it
            if "style" in payload and not payload["style"]:
                logger.info("Empty string provided for style, not adding to image_to_model payload")
            elif "style" in payload:
                image_model_payload["style"] = payload["style"]
            
            return await call_tripo_task_api("image_to_model", image_model_payload)
        else:
            # For multiple images, prepare files array for multiview
            files = []
            for i, url in enumerate(image_urls[:4]):  # Maximum 4 images
                files.append({"url": url, "type": "jpg"} if url else {})
            
            # Fill remaining positions with empty objects
            while len(files) < 4:
                files.append({})
                
            # Create a payload for multiview_to_model
            multiview_payload = {
                "files": files
            }
            
            # Copy key parameters from the original request
            if "prompt" in payload and payload["prompt"]:
                multiview_payload["prompt"] = payload["prompt"]
                
            if "texture" in payload:
                multiview_payload["texture"] = payload["texture"]
                
            # Remove empty style if present, otherwise copy it
            if "style" in payload and not payload["style"]:
                logger.info("Empty string provided for style, not adding to multiview_to_model payload")
            elif "style" in payload:
                multiview_payload["style"] = payload["style"]
            
            logger.info(f"Multiview with {len(files)} valid images")
            
            return await call_tripo_task_api("multiview_to_model", multiview_payload)
    else:
        logger.warning("No image_urls provided in request_data")
        return await call_tripo_task_api("multiview_to_model", payload)

async def generate_sketch_to_model(request_data: SketchToModelRequest) -> Dict[str, Any]:
    """Calls Tripo AI image-to-model endpoint.
    
    According to V2 API docs:
    - type: image_to_model
    - file: File info with URL
    - texture: boolean (optional)
    - Additional optional parameters
    
    NOTE: The Tripo API appears to ignore the texture parameter and always use textures.
    """
    # Start with all fields from the request model that are not None
    payload = request_data.model_dump(exclude_none=True)
    logger.info("Generating sketch-to-model with Tripo AI")

    # Restructure for the 'file' parameter as per Tripo API docs for image_to_model
    if "image_url" in payload:
        image_url_value = payload.pop("image_url")
        payload["file"] = {"url": image_url_value, "type": "png"} # Assuming PNG from OpenAI
        logger.info(f"Using image URL: {image_url_value} under file.url")
    else:
        # This case should ideally not happen if SketchToModelRequest requires image_url
        logger.error("image_url missing in SketchToModelRequest for generate_sketch_to_model")
        raise ValueError("image_url is required for sketch-to-model")

    # Remove parameters not supported by image_to_model or if we want default behavior
    if "prompt" in payload:
        logger.info("Removing 'prompt' from payload as it's not supported by image_to_model type.")
        payload.pop("prompt")
    
    if "style" in payload:
        logger.info("Removing 'style' from payload to use original image style (default behavior).")
        payload.pop("style")
        
    # 'texture' is a valid parameter, so it will be kept if present in request_data (defaults to True in schema)
    # Other valid parameters from SketchToModelRequest like model_version, pbr, etc., will be passed if not None.

    logger.info(f"Final payload keys for image_to_model: {list(payload.keys())}")
    if "file" in payload:
        logger.info(f"File parameter details: {payload['file']}")

    return await call_tripo_task_api("image_to_model", payload)

async def refine_model(request_data: RefineModelRequest) -> Dict[str, Any]:
    """Calls Tripo AI refine-model endpoint.
    
    According to V2 API docs:
    - type: refine_model
    - draft_model_task_id: Task ID of a draft model
    """
    payload = request_data.model_dump()
    logger.info("Refining model with Tripo AI")
    logger.info(f"Using draft model task ID: {payload.get('draft_model_task_id')}")
    return await call_tripo_task_api("refine_model", payload)

async def poll_tripo_task_status(task_id: str) -> Dict[str, Any]:
    """Polls Tripo AI for the status of a task according to V2 API documentation."""
    url = f"{TRIPO_API_BASE_URL_V2}/openapi/task/{task_id}"
    headers = {
        "Authorization": f"Bearer {settings.tripo_api_key}"
    }

    logger.info(f"Polling Tripo AI task status for ID: {task_id}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            
            response_data = response.json()
            
            # V2 API response structure: {"code": 0, "data": {...}}
            if "code" not in response_data or response_data.get("code") != 0:
                logger.warning(f"Unexpected response code from Tripo API: {response_data.get('code')}")
                
            data = response_data.get("data", {})
            if not data:
                logger.warning(f"Unexpected response format from Tripo API for task {task_id}: missing 'data' field")
                logger.warning(f"Response keys: {list(response_data.keys())}")
                
            # Extract fields according to V2 API documentation
            # status: queued, running, success, failed, cancelled, unknown
            status = data.get("status")
            progress = data.get("progress", 0)
            task_type = data.get("type")
            
            logger.info(f"Tripo AI task {task_id} status: {status}, progress: {progress}%, type: {task_type}")
            
            # Check for model URL in output as per documentation
            output = data.get("output", {})
            if output:
                # Log all available output fields
                logger.info(f"Tripo task output data available fields: {list(output.keys())}")
                
                if "model" in output:
                    logger.info(f"Tripo task model URL (from output.model): {output['model']}")
                if "base_model" in output:
                    logger.info(f"Tripo task base_model URL: {output['base_model']}")
                if "pbr_model" in output:
                    logger.info(f"Tripo task pbr_model URL: {output['pbr_model']}")
                if "rendered_image" in output:
                    logger.info(f"Tripo task rendered_image URL: {output['rendered_image']}")
            
            return response_data
    except httpx.HTTPStatusError as e:
        logger.error(f"Tripo AI HTTP error polling status for ID {task_id}: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise # Re-raise the exception after logging
    except Exception as e:
        logger.error(f"Error polling Tripo AI status for ID {task_id}: {e}", exc_info=True)
        raise # Re-raise the exception after logging

# Helper to normalize Tripo status response
def normalize_tripo_status(tripo_response: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes Tripo V2 API status response to a common format."""
    logger.info(f"normalize_tripo_status raw input: {tripo_response}")
    
    data = tripo_response.get("data", {})
    task_id = data.get("task_id", "unknown")
    
    # Extract status according to V2 API documentation
    # status: queued, running, success, failed, cancelled, unknown
    task_status = data.get("status")
    progress = data.get("progress", 0)
    
    # Extract model URL according to V2 API documentation
    # Per docs: output.model contains the model URL
    model_url = None
    output = data.get("output", {})
    
    # First check for pbr_model which is the primary field for textured models
    if isinstance(output, dict) and "pbr_model" in output:
        model_url = output["pbr_model"]
        logger.info(f"Found model URL in output.pbr_model for task {task_id}: {model_url}")
        
    # Check for base_model as alternative
    if not model_url and isinstance(output, dict) and "base_model" in output:
        model_url = output["base_model"]
        logger.info(f"Found model URL in output.base_model for task {task_id}: {model_url}")
    
    # Check for model field as documented
    if not model_url and isinstance(output, dict) and "model" in output:
        model_url = output["model"]
        logger.info(f"Found model URL in output.model for task {task_id}: {model_url}")
    
    # Check in the result object which contains structured data
    result = data.get("result", {})
    if not model_url and isinstance(result, dict):
        # Check pbr_model first (for textured models)
        if "pbr_model" in result and isinstance(result["pbr_model"], dict) and "url" in result["pbr_model"]:
            model_url = result["pbr_model"]["url"]
            logger.info(f"Found model URL in result.pbr_model.url for task {task_id}: {model_url}")
        # Then check base_model (for non-textured models)
        elif "base_model" in result and isinstance(result["base_model"], dict) and "url" in result["base_model"]:
            model_url = result["base_model"]["url"]
            logger.info(f"Found model URL in result.base_model.url for task {task_id}: {model_url}")
        # Finally check for model (generic field)
        elif "model" in result and isinstance(result["model"], dict) and "url" in result["model"]:
            model_url = result["model"]["url"]
            logger.info(f"Found model URL in result.model.url for task {task_id}: {model_url}")
    
    # Fallback checks for other possible URL locations
    if not model_url and isinstance(output, dict) and "url" in output:
        model_url = output["url"]
        logger.info(f"Found model URL in output.url for task {task_id}: {model_url}")
        
    if not model_url and isinstance(output, dict) and "model_url" in output:
        model_url = output["model_url"]
        logger.info(f"Found model URL in output.model_url for task {task_id}: {model_url}")
    
    # Check direct fields in data
    if not model_url and data.get("model_url"):
        model_url = data.get("model_url")
        logger.info(f"Found model URL directly in data.model_url for task {task_id}: {model_url}")
        
    if not model_url and data.get("url"):
        model_url = data.get("url")
        logger.info(f"Found model URL directly in data.url for task {task_id}: {model_url}")
    
    # Check if output itself is a URL string
    if not model_url and isinstance(output, str) and (output.startswith("http") or output.startswith("https")):
        model_url = output
        logger.info(f"Found model URL in output string for task {task_id}: {model_url}")
    
    # For testing purposes - for Tripo v2 API sometimes we need a hardcoded URL 
    # REMOVE THIS IN PRODUCTION
    if settings.tripo_test_mode and (task_status == "success" or progress == 100) and not model_url:
        # Use a publicly accessible sample GLB file for testing
        model_url = "https://storage.googleapis.com/materials-icons/external-assets/mocks/models/Duck.glb"
        logger.warning(f"TEST MODE: Using hardcoded sample model URL for task {task_id}: {model_url}")
    
    # Log extracted data fields for debugging
    logger.info(f"Tripo task {task_id} - Extracted data: status={task_status}, progress={progress}, model_url={model_url}")
    
    # Map Tripo statuses to our internal simplified statuses based on V2 API documentation
    status_map = {
        "queued": "pending",
        "running": "processing",
        "success": "completed",
        "failed": "failed",
        "cancelled": "failed",
        "unknown": "unknown"
    }
    
    # Normalize progress according to Tripo docs
    # - 0 when queued
    # - actual progress when running (0-100)
    # - 100 when success
    # - not meaningful otherwise (default to 0)
    normalized_progress = progress if isinstance(progress, (int, float)) else 0
    if task_status == "success":
        normalized_progress = 100
    
    # Determine status, with fallback to progress-based detection
    normalized_status = status_map.get(task_status, "unknown")
    
    # If status is unknown but progress is 100%, treat as completed
    if normalized_status == "unknown" and progress == 100:
        normalized_status = "completed"
        normalized_progress = 100
        logger.info(f"Overriding unknown status to completed based on 100% progress for task {task_id}")
    
    # If we have a model_url but status isn't completed, force completed status
    if model_url and normalized_status != "completed":
        normalized_status = "completed"
        normalized_progress = 100
        logger.info(f"Overriding status to completed because model_url is present for task {task_id}")
    
    # Always consider task completed in test mode with high progress
    if settings.tripo_test_mode and progress >= 95:
        normalized_status = "completed"
        normalized_progress = 100
        logger.warning(f"TEST MODE: Considering task {task_id} completed due to test mode and progress >= 95%")
    
    # Prepare the result
    result = {
        "status": normalized_status,
        "progress": normalized_progress,
        "result_url": model_url if normalized_status == "completed" else None,
    }
    
    # Add more detailed logging to show progress
    logger.info(f"Tripo task {task_id} status: {task_status} -> {normalized_status}, progress: {normalized_progress}%")
    
    return result 