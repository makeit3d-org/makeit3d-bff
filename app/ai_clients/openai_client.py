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
        "prompt": request_data.prompt,
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
    """Polls OpenAI for the status of an image generation task."""
    # OpenAI's image generation GET endpoint doesn't provide a detailed status like pending/processing,
    # it just returns the result if complete or an error if failed/invalid task ID.
    # We will treat a successful response as 'completed'.
    url = f"{OPENAI_API_BASE_URL}/images/generations/{task_id}" # Note: This GET endpoint seems non-standard based on current OpenAI docs, will rely on common pattern or re-check.
    # Re-checking OpenAI docs: The image generation (DALL-E) and edit API (`/v1/images/generations`, `/v1/images/edits`) do not have a separate GET status endpoint by ID in the standard way.
    # The initial POST call is synchronous for DALL-E 2 and 3, returning URLs directly.
    # The concept of polling by task_id for DALL-E edits might be based on a misunderstanding or a feature of a different OpenAI product/version.
    # Assuming for the MVP, the initial POST /generate/image-to-image will return the URLs synchronously as per standard DALL-E API behavior.
    # Therefore, a separate polling function for OpenAI image tasks might not be necessary for the MVP.
    # I will adjust the /generate/image-to-image endpoint and the status polling endpoint logic accordingly.

    # For now, leaving a placeholder function but the logic needs to be re-evaluated based on synchronous OpenAI image API behavior.
    logger.info(f"Attempting to poll status for OpenAI task ID: {task_id}. Note: OpenAI image APIs are typically synchronous.")
    # This function might not be called if the generate endpoint is synchronous.
    return {"status": "completed", "progress": 100.0, "result_url": None} # Return None for result_url as BFF doesn't store it 