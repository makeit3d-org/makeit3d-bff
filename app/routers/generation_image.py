import httpx
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request
from typing import List, Optional
import logging

# Test user ID for endpoints when auth is not implemented
TEST_USER_ID = "00000000-0000-4000-8000-000000000001"

# Explicitly import required schemas from the module (image-related only)
from app.schemas.generation_schemas import (
    ImageToImageRequest,
    TextToImageRequest,
    SketchToImageRequest,
    RemoveBackgroundRequest,
    ImageInpaintRequest,
    SearchAndRecolorRequest,
    TaskIdResponse,
)

# Import client functions for asynchronous mode (image-related only)
from app.ai_clients import openai_client
from app.ai_clients.stability_client import stability_client
from app.ai_clients.recraft_client import recraft_client
from app.config import settings # Import settings
from app.limiter import limiter # Import the limiter

import app.supabase_handler as supabase_handler # New Supabase handler

# Import only image-related tasks
from app.tasks.generation_tasks import (
    generate_openai_image_task,
    generate_stability_image_task,
    generate_recraft_image_task
)

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/image-to-image", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def generate_image_to_image_endpoint(
    request: Request, # FastAPI request object for context if needed (e.g., user)
    request_data: ImageToImageRequest # Updated to use Pydantic model from request body
):
    """Initiates concept image generation from an input image using multiple AI providers."""
    logger.info(f"Received request for /generate/image-to-image for task_id: {request_data.task_id} using provider: {request_data.provider}")
    user_id_from_auth = TEST_USER_ID

    # Fetch the image from Supabase first
    try:
        image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
        logger.info(f"Successfully fetched input image for task {request_data.task_id} from: {request_data.input_image_asset_url}")
    except HTTPException as e:
        logger.error(f"Failed to fetch image from Supabase for task {request_data.task_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching image for task {request_data.task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve input image.")

    try:
        # Create the record in concept_images table before dispatching the task
        # The Celery task ID will be added in a subsequent update.
        db_record = await supabase_handler.create_concept_image_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style,
            status="pending", # Initial status before Celery task ID is known
            user_id=user_id_from_auth, # Pass user_id if available
            # source_input_asset_id needs to be passed if available/required by schema
        )
        concept_image_db_id = db_record["id"]
        logger.info(f"Created concept image record {concept_image_db_id} for task {request_data.task_id}")
    except HTTPException as e:
        logger.error(f"Failed to create Supabase record for task {request_data.task_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating Supabase record for task {request_data.task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize task record.")

    logger.info(f"Sending {request_data.provider} image generation task to Celery for db_id: {concept_image_db_id}")
    
    if request_data.provider == "openai":
        celery_task = generate_openai_image_task.delay(
            concept_image_db_id=concept_image_db_id,
            image_bytes=image_bytes,
            original_filename=request_data.input_image_asset_url.split('/')[-1],
            request_data_dict=request_data.model_dump()
        )
    elif request_data.provider == "stability":
        celery_task = generate_stability_image_task.delay(
            concept_image_db_id=concept_image_db_id,
            image_bytes=image_bytes,
            request_data_dict=request_data.model_dump(),
            operation_type="image_to_image"
        )
    elif request_data.provider == "recraft":
        celery_task = generate_recraft_image_task.delay(
            concept_image_db_id=concept_image_db_id,
            image_bytes=image_bytes,
            request_data_dict=request_data.model_dump(),
            operation_type="image_to_image"
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {request_data.provider}")
        
    logger.info(f"Celery task ID: {celery_task.id} for concept_image_db_id: {concept_image_db_id}")

    # Update the Supabase record with the Celery task ID and set status to 'processing'
    try:
        await supabase_handler.update_concept_image_record(
            task_id=request_data.task_id, # Main client task_id
            concept_image_id=concept_image_db_id,
            status="processing", # Indicates task sent to Celery and being processed
            ai_service_task_id=celery_task.id
        )
        logger.info(f"Updated concept image record {concept_image_db_id} with Celery task ID {celery_task.id}")
    except Exception as e:
        # Log this error but proceed to return task ID to client, as Celery task is dispatched.
        # The task itself should handle failures gracefully.
        logger.error(f"Failed to update Supabase record {concept_image_db_id} with Celery task ID {celery_task.id}: {e}", exc_info=True)
        # Potentially raise an alert or specific monitoring event here.

    return TaskIdResponse(celery_task_id=celery_task.id)

@router.post("/text-to-image", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def generate_text_to_image_endpoint(request: Request, request_data: TextToImageRequest):
    """Initiates 2D image generation from text using multiple AI providers."""
    logger.info(f"Received request for /generate/text-to-image for task_id: {request_data.task_id} using provider: {request_data.provider}")
    user_id_from_auth = TEST_USER_ID

    # Validate provider
    if request_data.provider not in ["openai", "stability", "recraft"]:
        raise HTTPException(status_code=400, detail="text-to-image supports 'openai', 'stability', and 'recraft' providers")

    # Fetch the image from Supabase first
    try:
        image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
        logger.info(f"Successfully fetched input image for task {request_data.task_id} from: {request_data.input_image_asset_url}")
    except HTTPException as e:
        logger.error(f"Failed to fetch image from Supabase for task {request_data.task_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching image for task {request_data.task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve input image.")

    try:
        # Create the record in concept_images table before dispatching the task
        db_record = await supabase_handler.create_concept_image_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style,
            status="pending",
            user_id=user_id_from_auth,
            metadata={"provider": request_data.provider}
        )
        concept_image_db_id = db_record["id"]
        logger.info(f"Created concept image record {concept_image_db_id} for task {request_data.task_id}")

        logger.info(f"Sending {request_data.provider} text-to-image task to Celery for concept_image_db_id: {concept_image_db_id}")
        
        if request_data.provider == "openai":
            # For OpenAI text-to-image, we don't need image_bytes, so pass empty bytes
            celery_task = generate_openai_image_task.delay(
                concept_image_db_id=concept_image_db_id,
                image_bytes=b"",  # Empty bytes for text-to-image
                original_filename="",  # No filename for text-to-image
                request_data_dict=request_data.model_dump()
            )
        elif request_data.provider == "stability":
            celery_task = generate_stability_image_task.delay(
                concept_image_db_id=concept_image_db_id,
                image_bytes=b"",  # Empty bytes for text-to-image
                request_data_dict=request_data.model_dump(),
                operation_type="text_to_image"
            )
        elif request_data.provider == "recraft":
            celery_task = generate_recraft_image_task.delay(
                concept_image_db_id=concept_image_db_id,
                image_bytes=b"",  # Empty bytes for text-to-image
                request_data_dict=request_data.model_dump(),
                operation_type="text_to_image"
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {request_data.provider}")
            
        logger.info(f"Celery task ID: {celery_task.id} for concept_image_db_id: {concept_image_db_id}")

        # Update the Supabase record with the Celery task ID and set status to 'processing'
        await supabase_handler.update_concept_image_record(
            task_id=request_data.task_id,
            concept_image_id=concept_image_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        logger.info(f"Updated concept image record {concept_image_db_id} with Celery task ID {celery_task.id}")
        
        return TaskIdResponse(celery_task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /text-to-image endpoint for task {request_data.task_id}: {e}", exc_info=True)
        # Attempt to update status to failed if db_record was created
        if 'concept_image_db_id' in locals() and concept_image_db_id:
            try:
                await supabase_handler.update_concept_image_record(task_id=request_data.task_id, concept_image_id=concept_image_db_id, status="failed")
            except Exception as db_update_e:
                logger.error(f"Failed to update concept image record to failed: {db_update_e}")
        raise HTTPException(status_code=500, detail=f"Failed to process text-to-image request: {str(e)}")

@router.post("/sketch-to-image", response_model=TaskIdResponse)
async def generate_sketch_to_image_endpoint(request: Request, request_data: SketchToImageRequest):
    """Initiates 2D image generation from a single sketch image (Supabase URL) using Stability AI."""
    logger.info(f"Received request for /generate/sketch-to-image for task_id: {request_data.task_id}")
    user_id_from_auth = TEST_USER_ID

    # Fetch the image from Supabase first
    try:
        image_bytes, original_filename = await supabase_handler.fetch_asset_from_storage(request_data.input_sketch_asset_url)
        if not image_bytes:
            raise HTTPException(status_code=404, detail="Failed to fetch input sketch from Supabase for async mode.")
    except HTTPException as e:
        logger.error(f"Failed to fetch input sketch from Supabase for async mode: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching input sketch from Supabase for async mode: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve input sketch from Supabase for asynchronous processing.")

    try:
        # Create the record in concept_images table before dispatching the task
        db_record = await supabase_handler.create_concept_image_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style_preset,
            status="pending",
            user_id=user_id_from_auth
        )
        concept_image_db_id = db_record["id"]
        logger.info(f"Created concept image record {concept_image_db_id} for sketch-to-image task {request_data.task_id}")

        # Use Stability image task for sketch-to-image
        celery_task = generate_stability_image_task.delay(
            concept_image_db_id=concept_image_db_id,
            image_bytes=image_bytes,
            request_data_dict=request_data.model_dump(),
            operation_type="sketch_to_image"
        )
        logger.info(f"Celery task ID: {celery_task.id} for concept_image_db_id: {concept_image_db_id}")

        await supabase_handler.update_concept_image_record(
            task_id=request_data.task_id,
            concept_image_id=concept_image_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        return TaskIdResponse(celery_task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /sketch-to-image endpoint for task {request_data.task_id}: {e}", exc_info=True)
        if 'concept_image_db_id' in locals() and concept_image_db_id:
            try: await supabase_handler.update_concept_image_record(task_id=request_data.task_id, concept_image_id=concept_image_db_id, status="failed")
            except: pass
        raise HTTPException(status_code=500, detail=f"Failed to process sketch-to-image request: {str(e)}")

@router.post("/remove-background", response_model=TaskIdResponse)
async def remove_background_endpoint(request: Request, request_data: RemoveBackgroundRequest):
    """Remove background from an image using Stability AI or Recraft."""
    logger.info(f"Received request for /remove-background for task_id: {request_data.task_id}")
    user_id_from_auth = TEST_USER_ID

    # Fetch the image from Supabase first
    try:
        image_bytes, original_filename = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
        if not image_bytes:
            raise HTTPException(status_code=404, detail="Failed to fetch input image from Supabase for async mode.")
    except HTTPException as e:
        logger.error(f"Failed to fetch input image from Supabase for async mode: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching input image from Supabase for async mode: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve input image from Supabase for asynchronous processing.")

    try:
        # Create the record in concept_images table before dispatching the task
        db_record = await supabase_handler.create_concept_image_record(
            task_id=request_data.task_id,
            prompt="Remove background",
            style=None,
            status="pending",
            user_id=user_id_from_auth
        )
        concept_image_db_id = db_record["id"]
        logger.info(f"Created concept image record {concept_image_db_id} for remove-background task {request_data.task_id}")

        if request_data.provider == "stability":
            celery_task = generate_stability_image_task.delay(
                concept_image_db_id=concept_image_db_id,
                image_bytes=image_bytes,
                request_data_dict=request_data.model_dump(),
                operation_type="remove_background"
            )
        elif request_data.provider == "recraft":
            celery_task = generate_recraft_image_task.delay(
                concept_image_db_id=concept_image_db_id,
                image_bytes=image_bytes,
                request_data_dict=request_data.model_dump(),
                operation_type="remove_background"
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider for remove-background: {request_data.provider}")
            
        logger.info(f"Celery task ID: {celery_task.id} for concept_image_db_id: {concept_image_db_id}")

        await supabase_handler.update_concept_image_record(
            task_id=request_data.task_id,
            concept_image_id=concept_image_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        return TaskIdResponse(celery_task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /remove-background endpoint for task {request_data.task_id}: {e}", exc_info=True)
        if 'concept_image_db_id' in locals() and concept_image_db_id:
            try: await supabase_handler.update_concept_image_record(task_id=request_data.task_id, concept_image_id=concept_image_db_id, status="failed")
            except: pass
        raise HTTPException(status_code=500, detail=f"Failed to process remove-background request: {str(e)}")

@router.post("/image-inpaint", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def image_inpaint_endpoint(request: Request, request_data: ImageInpaintRequest):
    """Inpaints an image using a mask with Recraft AI."""
    logger.info(f"Received request for /image-inpaint for task_id: {request_data.task_id} using provider: {request_data.provider}")
    user_id_from_auth = TEST_USER_ID

    # Validate provider
    if request_data.provider != "recraft":
        raise HTTPException(status_code=400, detail="Only 'recraft' provider is supported for image-inpaint")

    # Fetch the image from Supabase first
    try:
        image_bytes, original_filename = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
        mask_bytes, mask_filename = await supabase_handler.fetch_asset_from_storage(request_data.input_mask_asset_url)
        logger.info(f"Successfully fetched input image and mask for async Recraft inpaint task {request_data.task_id}")
    except HTTPException as e:
        logger.error(f"Failed to fetch input assets from Supabase for async task {request_data.task_id}: {e.detail}")
        raise HTTPException(status_code=404, detail="Failed to fetch input image or mask from Supabase for asynchronous processing.")

    try:
        # Create the record in concept_images table before dispatching the task
        db_record = await supabase_handler.create_concept_image_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style,
            status="pending",
            user_id=user_id_from_auth
        )
        concept_image_db_id = db_record["id"]
        logger.info(f"Created concept image record {concept_image_db_id} for image-inpaint task {request_data.task_id}")

        # Use Recraft image task with inpaint operation
        from app.tasks.generation_tasks import generate_recraft_image_task
        
        # We need to pass both image and mask bytes - we'll modify the task to handle this
        # For now, we'll pass the mask bytes in the metadata and handle it in the task
        request_data_with_mask = request_data.model_dump()
        request_data_with_mask["mask_bytes"] = mask_bytes
        
        celery_task = generate_recraft_image_task.delay(
            concept_image_db_id=concept_image_db_id,
            image_bytes=image_bytes,
            request_data_dict=request_data_with_mask,
            operation_type="inpaint"
        )
            
        logger.info(f"Celery task ID: {celery_task.id} for concept_image_db_id: {concept_image_db_id}")

        await supabase_handler.update_concept_image_record(
            task_id=request_data.task_id,
            concept_image_id=concept_image_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        return TaskIdResponse(celery_task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /image-inpaint endpoint for task {request_data.task_id}: {e}", exc_info=True)
        if 'concept_image_db_id' in locals() and concept_image_db_id:
            try: await supabase_handler.update_concept_image_record(task_id=request_data.task_id, concept_image_id=concept_image_db_id, status="failed")
            except: pass
        raise HTTPException(status_code=500, detail=f"Failed to process image-inpaint request: {str(e)}")

@router.post("/search-and-recolor", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def search_and_recolor_endpoint(request: Request, request_data: SearchAndRecolorRequest):
    """Search for objects in an image and recolor them using Stability AI."""
    operation_id = f"search-recolor-{request_data.task_id}"
    logger.info(f"Received search-and-recolor request for task {request_data.task_id} (Operation ID: {operation_id})")
    
    if request_data.provider != "stability":
        logger.error(f"Invalid provider '{request_data.provider}' for search-and-recolor. Only 'stability' is supported.")
        raise HTTPException(status_code=400, detail="Search-and-recolor is only supported by Stability AI provider.")

    # Fetch the image from Supabase first
    try:
        image_bytes, original_filename = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
        logger.info(f"Successfully fetched input image for async search-and-recolor task {operation_id}")
    except HTTPException as e:
        logger.error(f"Failed to fetch input image from Supabase for async task {operation_id}: {e.detail}")
        raise HTTPException(status_code=404, detail="Failed to fetch input image from Supabase for asynchronous processing.")

    try:
        # Create the record in concept_images table before dispatching the task
        db_record = await supabase_handler.create_concept_image_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style_preset,
            status="queued",
            user_id="default_user_id",
            metadata={"async_mode": True, "provider": "stability", "operation": "search_and_recolor"}
        )
        concept_image_db_id = db_record["id"]
        logger.info(f"Created concept image DB record {concept_image_db_id} for async task {operation_id}")

        # Convert request data to dict for Celery serialization
        request_data_dict = request_data.model_dump()

        # Queue the Celery task
        celery_task = generate_stability_image_task.delay(
            concept_image_db_id, 
            image_bytes, 
            request_data_dict, 
            "search_and_recolor"
        )
        celery_task_id = celery_task.id
        logger.info(f"Queued async Stability search-and-recolor task {celery_task_id} for DB record {concept_image_db_id}")

        # Update the DB record with the Celery task ID
        await supabase_handler.update_concept_image_record(
            task_id=request_data.task_id,
            concept_image_id=concept_image_db_id,
            ai_service_task_id=celery_task_id,
            status="queued"
        )
        logger.info(f"Updated concept image DB record {concept_image_db_id} with Celery task ID {celery_task_id}")

        return TaskIdResponse(celery_task_id=celery_task_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /search-and-recolor endpoint for task {request_data.task_id}: {e}", exc_info=True)
        if 'concept_image_db_id' in locals() and concept_image_db_id:
            try: await supabase_handler.update_concept_image_record(task_id=request_data.task_id, concept_image_id=concept_image_db_id, status="failed")
            except: pass
        raise HTTPException(status_code=500, detail=f"Failed to process search-and-recolor request: {str(e)}")


# The /select-concept endpoint and its associated Celery task import have been removed.
# The SelectConceptRequest schema import is also removed from app.schemas.generation_schemas. 