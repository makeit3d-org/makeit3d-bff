# https://docs.bfl.ai/api-reference/tasks/edit-or-create-an-image-with-flux-kontext-pro

import httpx
import base64
import asyncio
from typing import Dict, Any, Optional
import logging

from config import settings
from schemas.generation_schemas import (
    ImageToImageRequest,
    TextToImageRequest
)

logger = logging.getLogger(__name__)

FLUX_API_BASE_URL = "https://api.bfl.ai/v1"

async def generate_image_to_image_flux(
    image_bytes: bytes, 
    request_model: ImageToImageRequest
) -> Dict[str, Any]:
    """
    Calls Flux Kontext Pro image-to-image endpoint.
    
    Args:
        image_bytes: Input image as bytes
        request_model: Request parameters
        
    Returns:
        Dict containing task_id and polling_url
    """
    logger.info("Generating image-to-image with Flux Kontext Pro")
    
    # Convert image to base64
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    url = f"{FLUX_API_BASE_URL}/flux-kontext-pro"
    headers = {
        "x-key": settings.FLUX_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Extract Flux-specific parameters or use defaults
    payload = {
        "prompt": request_model.prompt,
        "input_image": image_b64,
        "aspect_ratio": getattr(request_model, 'aspect_ratio', "1:1"),
        "output_format": getattr(request_model, 'output_format', "png"),
        "safety_tolerance": getattr(request_model, 'safety_tolerance', 2),
        "prompt_upsampling": getattr(request_model, 'prompt_upsampling', False)
    }
    
    # Add optional seed if provided
    if hasattr(request_model, 'seed') and request_model.seed is not None:
        payload["seed"] = request_model.seed
    
    logger.info(f"Calling Flux API: {url}")
    logger.info(f"Prompt: {request_model.prompt}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            response_data = response.json()
            logger.info(f"Flux API response: {response_data}")
            
            # Validate response contains required fields
            if "id" not in response_data or "polling_url" not in response_data:
                logger.error(f"Invalid Flux API response: {response_data}")
                raise ValueError(f"Flux API response missing required fields: {response_data}")
            
            return response_data
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Flux API HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Error calling Flux API: {e}")
        raise

async def generate_text_to_image_flux(request_model: TextToImageRequest) -> Dict[str, Any]:
    """
    Calls Flux text-to-image endpoint (using Flux Pro or other text-to-image models).
    
    Args:
        request_model: Request parameters
        
    Returns:
        Dict containing task_id and polling_url
    """
    logger.info("Generating text-to-image with Flux")
    
    # For text-to-image, we might use a different endpoint like flux-pro
    # For now, I'll implement this as a placeholder since the test was image-to-image
    url = f"{FLUX_API_BASE_URL}/flux-pro"  # This might be different
    headers = {
        "x-key": settings.FLUX_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": request_model.prompt,
        "width": getattr(request_model, 'width', 1024),
        "height": getattr(request_model, 'height', 1024),
        "safety_tolerance": getattr(request_model, 'safety_tolerance', 2),
        "prompt_upsampling": getattr(request_model, 'prompt_upsampling', False)
    }
    
    # Add optional seed if provided
    if hasattr(request_model, 'seed') and request_model.seed is not None:
        payload["seed"] = request_model.seed
    
    logger.info(f"Calling Flux text-to-image API: {url}")
    logger.info(f"Prompt: {request_model.prompt}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            response_data = response.json()
            logger.info(f"Flux text-to-image API response: {response_data}")
            
            if "id" not in response_data or "polling_url" not in response_data:
                logger.error(f"Invalid Flux API response: {response_data}")
                raise ValueError(f"Flux API response missing required fields: {response_data}")
            
            return response_data
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Flux text-to-image API HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Error calling Flux text-to-image API: {e}")
        raise

async def poll_flux_task_status(polling_url: str) -> Dict[str, Any]:
    """
    Polls Flux API for task completion status.
    
    Args:
        polling_url: The polling URL returned from Flux API
        
    Returns:
        Dict containing status and result data
    """
    headers = {
        "x-key": settings.FLUX_API_KEY
    }
    
    logger.info(f"Polling Flux task status: {polling_url}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(polling_url, headers=headers)
            response.raise_for_status()
            
            response_data = response.json()
            logger.info(f"Flux polling response: {response_data}")
            
            return response_data
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Flux polling HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Error polling Flux task: {e}")
        raise

def normalize_flux_status(flux_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes Flux API status response to common format.
    
    Args:
        flux_response: Raw response from Flux polling API
        
    Returns:
        Normalized response with status and image_url
    """
    status = flux_response.get("status", "unknown")
    
    # Map Flux statuses to our internal format
    status_map = {
        "Pending": "processing",
        "Ready": "complete", 
        "Error": "failed",
        "Failed": "failed"
    }
    
    normalized_status = status_map.get(status, "processing")
    
    # Extract image URL if ready
    image_url = None
    if normalized_status == "complete":
        result = flux_response.get("result", {})
        if isinstance(result, dict):
            image_url = result.get("sample")
        elif isinstance(result, str):
            image_url = result
    
    # Extract error if failed
    error_message = None
    if normalized_status == "failed":
        error_message = flux_response.get("error", "Unknown Flux error")
    
    return {
        "status": normalized_status,
        "image_url": image_url,
        "error": error_message,
        "raw_response": flux_response
    } 