from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from typing import List, Optional
import logging
import hash

from ..schemas.generation_schemas import (
    TextToModelRequest,
    ImageToModelRequest,
    SketchToModelRequest,
    RefineModelRequest,
    TaskIdResponse,
    ImageToImageResponse, # Assuming synchronous response for now
    SelectConceptRequest
)
from ..ai_clients import openai_client, tripo_client

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/image-to-image", response_model=ImageToImageResponse)
async def generate_image_to_image_endpoint(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    style: Optional[str] = Form(None)
):
    """Generates 2D concepts from an input image and text prompt using OpenAI.
    Handles multipart/form-data for the image file.
    """
    logger.info("Received request for /generate/image-to-image")
    # Read image file content
    image_bytes = await image.read()

    # Prepare data for client (excluding file which is handled separately)
    request_data = ImageToImageRequest(prompt=prompt, style=style)

    try:
        # Call OpenAI client - assuming synchronous response based on documentation review
        openai_response = await openai_client.generate_image_to_image(
            image_bytes, image.filename, request_data
        )
        # OpenAI returns a list of URLs directly for DALL-E edit
        image_urls = [item["url"] for item in openai_response.get("data", [])]

        # For synchronous OpenAI, we might not have a task_id in the same sense as Tripo.
        # We can potentially create a local task ID or just return the URLs directly.
        # Let's return URLs directly for MVP simplicity, as polling is not needed for this sync API.
        # However, the schema expects task_id. This indicates a potential mismatch or a need to simulate task_id for consistency.
        # Let's create a simple dummy task_id for the response consistency, but note it's not used for polling OpenAI.
        dummy_task_id = f"openai-img-{hash(tuple(image_urls))}" # Example dummy ID
        logger.info(f"Generated dummy OpenAI task ID: {dummy_task_id}")
        logger.info(f"Returning {len(image_urls)} image URLs for /generate/image-to-image")
        return ImageToImageResponse(task_id=dummy_task_id, image_urls=image_urls)

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in /generate/image-to-image: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenAI API error: {e.response.text}")
    except Exception as e:
        logger.error(f"Error in /generate/image-to-image: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.post("/text-to-model", response_model=TaskIdResponse)
async def generate_text_to_model_endpoint(request_data: TextToModelRequest):
    """Initiates 3D model generation from text using Tripo AI."""
    logger.info("Received request for /generate/text-to-model")
    try:
        tripo_response = await tripo_client.generate_text_to_model(request_data)
        task_id = tripo_response["data"]["task_id"]
        logger.info(f"Initiated Tripo AI text-to-model task with ID: {task_id}")
        return TaskIdResponse(task_id=task_id)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in /generate/text-to-model: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(status_code=e.response.status_code, detail=f"Tripo AI API error: {e.response.text}")
    except Exception as e:
        logger.error(f"Error in /generate/text-to-model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.post("/image-to-model", response_model=TaskIdResponse)
async def generate_image_to_model_endpoint(request_data: ImageToModelRequest):
    """Initiates 3D model generation from multiple images (multiview) using Tripo AI."""
    logger.info("Received request for /generate/image-to-model (multiview)")
    try:
        # Frontend provides image_urls, pass directly to Tripo client
        tripo_response = await tripo_client.generate_image_to_model(request_data)
        task_id = tripo_response["data"]["task_id"]
        logger.info(f"Initiated Tripo AI image-to-model (multiview) task with ID: {task_id}")
        return TaskIdResponse(task_id=task_id)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in /generate/image-to-model (multiview): {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(status_code=e.response.status_code, detail=f"Tripo AI API error: {e.response.text}")
    except Exception as e:
        logger.error(f"Error in /generate/image-to-model (multiview): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.post("/sketch-to-model", response_model=TaskIdResponse)
async def generate_sketch_to_model_endpoint(request_data: SketchToModelRequest):
    """Initiates 3D model generation from a single sketch image using Tripo AI."""
    logger.info("Received request for /generate/sketch-to-model")
    try:
        # Frontend provides image_url, pass directly to Tripo client
        tripo_response = await tripo_client.generate_sketch_to_model(request_data)
        task_id = tripo_response["data"]["task_id"]
        logger.info(f"Initiated Tripo AI sketch-to-model task with ID: {task_id}")
        return TaskIdResponse(task_id=task_id)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in /generate/sketch-to-model: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(status_code=e.response.status_code, detail=f"Tripo AI API error: {e.response.text}")
    except Exception as e:
        logger.error(f"Error in /generate/sketch-to-model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.post("/refine-model", response_model=TaskIdResponse)
async def refine_model_endpoint(request_data: RefineModelRequest):
    """Initiates refinement of a 3D model using Tripo AI."""
    logger.info("Received request for /generate/refine-model")
    try:
        # Frontend provides draft_model_task_id, pass directly to Tripo client
        tripo_response = await tripo_client.refine_model(request_data)
        task_id = tripo_response["data"]["task_id"]
        logger.info(f"Initiated Tripo AI refine-model task with ID: {task_id}")
        return TaskIdResponse(task_id=task_id)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in /generate/refine-model: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(status_code=e.response.status_code, detail=f"Tripo AI API error: {e.response.text}")
    except Exception as e:
        logger.error(f"Error in /generate/refine-model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@router.post("/select-concept", response_model=TaskIdResponse)
async def select_concept_endpoint(request_data: SelectConceptRequest):
    """Handles selection of a 2D concept and initiates 3D generation from it using Tripo AI."""
    logger.info("Received request for /generate/select-concept")
    # This endpoint receives the selected concept image URL from the frontend
    # and should call the Tripo AI image-to-model endpoint.

    # Create a request object suitable for the image-to-model client function
    # Note: Tripo's image-to-model (single image) endpoint expects `image_url` string, not list.
    # Tripo's multiview-to-model expects `image_urls` list.
    # Based on frontend flow (selecting a *single* concept), image-to-model (single image) seems appropriate.
    # However, the frontend architecture mentions image-to-model from *multiple* images for photo-to-model.
    # Let's assume `select-concept` uses the single image endpoint (`image-to-model`).
    tripo_image_to_model_request = SketchToModelRequest(
        image_url=request_data.selected_image_url, # Use the selected concept URL
        # Assuming prompt/style might be carried over or are optional for image-to-model from concept
        prompt=None, # Adjust if prompt/style are needed
        style=None, # Adjust if prompt/style are needed
        texture=True # Adjust if texture is configurable
    )

    try:
        logger.info(f"Calling Tripo AI image-to-model from concept URL: {request_data.selected_image_url}")
        tripo_response = await tripo_client.generate_sketch_to_model(tripo_image_to_model_request)
        task_id = tripo_response["data"]["task_id"]
        logger.info(f"Initiated Tripo AI image-to-model task from concept with ID: {task_id}")
        return TaskIdResponse(task_id=task_id)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in /generate/select-concept: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(status_code=e.response.status_code, detail=f"Tripo AI API error: {e.response.text}")
    except Exception as e:
        logger.error(f"Error in /generate/select-concept: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 