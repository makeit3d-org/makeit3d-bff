import httpx
from typing import List, Dict, Any
import logging

from ..config import settings
from ..schemas.generation_schemas import ImageToImageRequest

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
        "n": 2,
        "size": "256x256",
        "response_format": "url",
    }
    # Note: Mask parameter is not included as per BFF architecture doc

    logger.info(f"Calling OpenAI Image Edit API: {url}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, files=files, data=data)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            logger.info(f"OpenAI Image Edit API response status: {response.status_code}")
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