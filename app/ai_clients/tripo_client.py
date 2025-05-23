import httpx
from typing import Dict, Any, List, Optional
import logging
import json
import base64

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

async def generate_image_to_model(
    image_files_data: List[bytes], 
    image_filenames: List[str], 
    request_model: ImageToModelRequest
) -> Dict[str, Any]:
    """Calls Tripo AI image-to-model or multiview-to-model endpoint using base64 data URIs."""
    
    payload_params = request_model.model_dump(exclude_none=True, exclude={"input_image_asset_urls"}) # Base parameters
    logger.info("Generating image-to-model with Tripo AI using image data.")

    if not image_files_data or not isinstance(image_files_data, list) or len(image_files_data) == 0:
        logger.error("No image data provided for generate_image_to_model")
        raise ValueError("image_files_data is required and must be a non-empty list")

    if len(image_files_data) == 1:
        logger.info("Single image provided, using image_to_model API type.")
        image_bytes = image_files_data[0]
        # Assuming PNG or JPG based on common use cases. For more robustness, original_filenames could inform this.
        # Defaulting to image/jpeg as a common format. Consider making this dynamic based on filename extension.
        mime_type = "image/jpeg" 
        if image_filenames and image_filenames[0].lower().endswith(".png"):
            mime_type = "image/png"
        
        data_uri = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode()}"
        
        api_payload = {"file": data_uri}
        api_payload.update(payload_params) # Add other params like prompt, texture, style etc.
        
        # Clean up style if empty for image_to_model
        if api_payload.get('style') == "":
            logger.info("Empty string provided for style, removing from image_to_model payload")
            api_payload.pop('style')
            
        return await call_tripo_task_api("image_to_model", api_payload)
    else:
        logger.info(f"Multiple images ({len(image_files_data)}) provided, using multiview_to_model API type.")
        logger.info(f"Multiview image ordering ENFORCED: [front, left, back, right] - client must provide URLs in this exact order")
        
        # According to Tripo v2 API docs, multiview_to_model expects exactly 4 files in order [front, left, back, right]
        # We need to format them as objects with file data URIs
        files_list = []
        view_names = ["front", "left", "back", "right"]
        
        for i in range(4):  # Always expect 4 positions for multiview
            if i < len(image_files_data):
                # We have an image for this position
                img_bytes = image_files_data[i]
                mime_type = "image/jpeg"
                if image_filenames and i < len(image_filenames) and image_filenames[i].lower().endswith(".png"):
                    mime_type = "image/png"
                data_uri = f"data:{mime_type};base64,{base64.b64encode(img_bytes).decode()}"
                
                # For multiview, we try the data URI approach first
                # If this doesn't work, we may need to implement proper file upload to get file_token
                files_list.append({
                    "type": "jpg" if mime_type == "image/jpeg" else "png",
                    "url": data_uri  # Using data URI - may need file_token instead
                })
                logger.info(f"✓ Added {view_names[i]} view (position {i}) from client URL #{i}")
            else:
                # Empty position - according to docs, front cannot be omitted but others can
                if i == 0:  # front position cannot be empty
                    raise ValueError("Front view (first image) is required for multiview_to_model - client must provide at least 1 image URL in position 0 (front)")
                files_list.append({})  # Empty object for missing views
                logger.info(f"○ Position {i} ({view_names[i]}) left empty - fewer than {i+1} images provided by client")
        
        api_payload = {"files": files_list}
        api_payload.update(payload_params) # Add other params

        # Clean up style if empty for multiview_to_model
        if api_payload.get('style') == "":
            logger.info("Empty string provided for style, removing from multiview_to_model payload")
            api_payload.pop('style')

        logger.info(f"Multiview payload structure: {len([f for f in files_list if f])} non-empty views out of 4 positions")
        logger.info(f"View mapping: {[(i, view_names[i], '✓' if i < len(image_files_data) else '○') for i in range(4)]}")
        return await call_tripo_task_api("multiview_to_model", api_payload)

async def generate_sketch_to_model(
    image_bytes: bytes, 
    original_filename: str, # Used to infer mime_type, can be simple like "sketch.png"
    request_model: SketchToModelRequest
) -> Dict[str, Any]:
    """Calls Tripo AI image-to-model endpoint using base64 data URI for a sketch."""
    
    payload_params = request_model.model_dump(exclude_none=True, exclude={"input_sketch_asset_url"})
    logger.info("Generating sketch-to-model with Tripo AI using image data.")

    # Determine MIME type (default to image/png for sketches)
    mime_type = "image/png" 
    if original_filename and original_filename.lower().endswith(".jpg") or original_filename.lower().endswith(".jpeg"):
        mime_type = "image/jpeg"
        
    data_uri = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode()}"
    
    # Prepare payload for "image_to_model" task type
    # Based on fal.ai docs, if an API accepts a URL, it can also accept a data URI string directly.
    # So, `payload["file"]` should be the data_uri string.
    api_payload = {"file": data_uri}
    api_payload.update(payload_params) # Add other params like texture, pbr etc.

    # Remove parameters not typically supported/used by image_to_model for sketches or if we want default behavior
    # Prompt is often not used when an image is the primary driver.
    if "prompt" in api_payload:
        logger.info("Removing 'prompt' from payload for sketch_to_model (image_to_model type).")
        api_payload.pop("prompt")
    
    # Style is also often intrinsic to the sketch image.
    if "style" in api_payload:
        logger.info("Removing 'style' from payload for sketch_to_model (image_to_model type) to use image style.")
        api_payload.pop("style")

    logger.info(f"Final payload keys for image_to_model (sketch): {list(api_payload.keys())}")
    if "file" in api_payload:
        logger.info(f"File parameter is a data URI (length: {len(api_payload['file'])})")

    return await call_tripo_task_api("image_to_model", api_payload)

async def refine_model(
    model_bytes: bytes, 
    original_filename: str, # e.g. "input_model.glb"
    request_model: RefineModelRequest
) -> Dict[str, Any]:
    """Calls Tripo AI refine-model endpoint.
       This version assumes refine_model might take a model via data URI or requires a draft_model_task_id.
       The V2 docs for `refine_model` type mention `draft_model_task_id`.
       If direct model upload is needed for refinement (not via prior task_id), API needs clarification.
       For now, this function will attempt to pass model as data URI if `draft_model_task_id` is not primary.
       However, the primary path for `refine_model` in V2 is `draft_model_task_id`.
    """
    # Primary V2 API for refine_model is by draft_model_task_id
    if request_model.draft_model_task_id:
        logger.info(f"Refining model with Tripo AI using draft_model_task_id: {request_model.draft_model_task_id}")
        payload = {"draft_model_task_id": request_model.draft_model_task_id}
        # Add other refine-specific parameters from request_model if any (e.g. prompt, texture - check Tripo docs for refine_model)
        if request_model.prompt: # Prompt for refinement
            payload["prompt"] = request_model.prompt
        # Add texture, pbr etc. if applicable to refine_model type and present in request_model
        refine_options = request_model.model_dump(exclude_none=True, exclude={'input_model_asset_url', 'draft_model_task_id', 'prompt'})
        payload.update(refine_options)
        return await call_tripo_task_api("refine_model", payload)
    else:
        # This path is speculative: if refine_model could take a model file directly via data URI.
        # Tripo V2 docs emphasize draft_model_task_id for refine. This path might not be supported.
        logger.warning("Attempting refine_model with direct model data (data URI) - V2 API primarily uses draft_model_task_id. This may not be supported.")
        mime_type = "model/gltf-binary" # Assuming GLB for models
        data_uri = f"data:{mime_type};base64,{base64.b64encode(model_bytes).decode()}"

        payload = {"file": data_uri} # Hypothetical: if refine_model takes a 'file' like image_to_model
        # Add other parameters from request_model
        refine_params = request_model.model_dump(exclude_none=True, exclude={'input_model_asset_url', 'draft_model_task_id'})
        payload.update(refine_params)

        # It's more likely that to refine an arbitrary model not from a Tripo task, one would first
        # need to create a task from that model (e.g. an equivalent of image_to_model but for models),
        # get a task_id, and then use that as draft_model_task_id.
        # For now, calling with "refine_model" but this is unlikely to work without a draft_model_task_id.
        logger.error("Refine model called without draft_model_task_id. This usage is likely incorrect for Tripo V2 API.")
        raise ValueError("draft_model_task_id is required for Tripo V2 refine_model API type.")

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
        "success": "complete",
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
    
    # If status is unknown but progress is 100%, treat as complete
    if normalized_status == "unknown" and progress == 100:
        normalized_status = "complete"
        normalized_progress = 100
        logger.info(f"Overriding unknown status to complete based on 100% progress for task {task_id}")
    
    # If we have a model_url but status isn't complete, force complete status
    if model_url and normalized_status != "complete":
        normalized_status = "complete"
        normalized_progress = 100
        logger.info(f"Overriding status to complete because model_url is present for task {task_id}")
    
    # Always consider task complete in test mode with high progress
    if settings.tripo_test_mode and progress >= 95:
        normalized_status = "complete"
        normalized_progress = 100
        logger.warning(f"TEST MODE: Considering task {task_id} complete due to test mode and progress >= 95%")
    
    # Prepare the result
    result = {
        "status": normalized_status,
        "progress": normalized_progress,
        "result_url": model_url if normalized_status == "complete" else None,
    }
    
    # Add more detailed logging to show progress
    logger.info(f"Tripo task {task_id} status: {task_status} -> {normalized_status}, progress: {normalized_progress}%")
    
    return result 