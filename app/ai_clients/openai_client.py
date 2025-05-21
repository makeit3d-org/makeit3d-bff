import httpx
from typing import List, Dict, Any
import logging

from app.config import settings
from app.schemas.generation_schemas import ImageToImageRequest

logger = logging.getLogger(__name__)

OPENAI_API_BASE_URL = "https://api.openai.com/v1"

async def generate_image_to_image(image_file: bytes, filename: str, request_data: ImageToImageRequest) -> Dict[str, Any]:
    """Calls OpenAI's image edit API to generate concepts."""
    url = f"{OPENAI_API_BASE_URL}/images/edits"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}"
    }
    files = {
        "image": (filename, image_file, "image/png"), # Assuming PNG for sketch/image input
    }
    data = {
        "prompt": f"{request_data.prompt} Style: {request_data.style}" if request_data.style else request_data.prompt,
        "model": "gpt-image-1",
        "n": request_data.n,
        "size": "auto",
        # Default to b64_json for gpt-image-1, which is what we expect for Supabase upload
        # No explicit response_format needed as gpt-image-1 always returns b64_json
    }

    # Add background if provided
    if request_data.background:
        data["background"] = request_data.background
        # If background is transparent, ensure response_format implies PNG (default for gpt-image-1)
        # OpenAI docs state: "If transparent, the output format needs to support transparency, 
        # so it should be set to either png (default value) or webp."
        # gpt-image-1 already returns b64_json (which will be PNG data), so no explicit format change needed.
        logger.info(f"Using background: {request_data.background}")

    # Note: Mask parameter is not included as per BFF architecture doc

    logger.info(f"Calling OpenAI Image Edit API: {url}")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, files=files, data=data)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            logger.info(f"OpenAI Image Edit API response status: {response.status_code}")
            # For gpt-image-1, the response contains 'data' as a list of objects with 'b64_json'
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenAI HTTP error: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise # Re-raise the exception after logging
    except Exception as e:
        logger.error(f"Error calling OpenAI Image Edit API: {e}", exc_info=True)
        raise # Re-raise the exception after logging

async def poll_image_to_image_status(task_id: str) -> Dict[str, Any]:
    """Simulates polling for OpenAI image generation task status (synchronous API)."""
    # OpenAI's image generation and edit APIs (DALL-E) are synchronous and return results directly.
    # Polling is not required for these tasks. This function exists to satisfy the polling endpoint structure.
    logger.info(f"Status requested for OpenAI task ID: {task_id}. OpenAI image APIs are synchronous, status is always 'completed'.")
    # Return a simulated completed status.
    return {"status": "completed", "progress": 100.0, "result_url": None} # Return None for result_url as BFF doesn't store it 