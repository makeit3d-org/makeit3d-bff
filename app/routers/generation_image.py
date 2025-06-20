import httpx
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request, Depends
from typing import List, Optional
import logging
import base64

# Import authentication
from auth import get_current_tenant, TenantContext

# Test user ID for endpoints when auth is not implemented (kept for backward compatibility)
TEST_USER_ID = "00000000-0000-4000-8000-000000000001"

# Explicitly import required schemas from the module (image-related only)
from schemas.generation_schemas import (
    ImageToImageRequest,
    TextToImageRequest,
    SketchToImageRequest,
    RemoveBackgroundRequest,
    ImageInpaintRequest,
    SearchAndRecolorRequest,
    UpscaleRequest,
    DownscaleRequest,
    TaskIdResponse,
)

# Import client functions for asynchronous mode (image-related only)
from ai_clients import openai_client
from ai_clients.stability_client import stability_client
from ai_clients.recraft_client import recraft_client
from config import settings # Import settings
from limiter import limiter # Import the limiter

import supabase_handler # New Supabase handler

# Import only image-related tasks
from tasks.generation_image_tasks import (
    generate_openai_image_task,
    generate_stability_image_task,
    generate_recraft_image_task,
    generate_flux_image_task,
    generate_downscale_image_task
)

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/image-to-image", response_model=TaskIdResponse, include_in_schema=False)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def generate_image_to_image_endpoint(
    request: Request, # FastAPI request object for context if needed (e.g., user)
    request_data: ImageToImageRequest, # Updated to use Pydantic model from request body
    tenant: TenantContext = Depends(get_current_tenant) # Authentication dependency
):
    """Initiates concept image generation from an input image using multiple AI providers."""
    logger.info(f"Received request for /generate/image-to-image for task_id: {request_data.task_id} using provider: {request_data.provider} from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()

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
        # Create the record in images table before dispatching the task
        # The Celery task ID will be added in a subsequent update.
        db_record = await supabase_handler.create_image_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style,
            status="pending", # Initial status before Celery task ID is known
            user_id=user_id_from_auth, # Pass user_id if available
            image_type="ai_generated",  # Specify this is an AI generated image
            # source_input_asset_id needs to be passed if available/required by schema
        )
        image_db_id = db_record["id"]
        logger.info(f"Created image record {image_db_id} for task {request_data.task_id}")
    except HTTPException as e:
        logger.error(f"Failed to create Supabase record for task {request_data.task_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating Supabase record for task {request_data.task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize task record.")

    logger.info(f"Sending {request_data.provider} image generation task to Celery for db_id: {image_db_id}")
    
    if request_data.provider == "openai":
        celery_task = generate_openai_image_task.delay(
            image_db_id,
            base64.b64encode(image_bytes).decode('utf-8'),
            request_data.input_image_asset_url.split('/')[-1],
            request_data.model_dump()
        )
    elif request_data.provider == "stability":
        celery_task = generate_stability_image_task.delay(
            image_db_id,
            base64.b64encode(image_bytes).decode('utf-8'),
            request_data.model_dump(),
            "image_to_image"
        )
    elif request_data.provider == "recraft":
        celery_task = generate_recraft_image_task.delay(
            image_db_id,
            base64.b64encode(image_bytes).decode('utf-8'),
            request_data.model_dump(),
            "image_to_image"
        )
    elif request_data.provider == "flux":
        celery_task = generate_flux_image_task.delay(
            image_db_id,
            base64.b64encode(image_bytes).decode('utf-8'),
            request_data.model_dump(),
            "image_to_image"
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {request_data.provider}")
        
    logger.info(f"Celery task ID: {celery_task.id} for image_db_id: {image_db_id}")

    # Update the Supabase record with the Celery task ID and set status to 'processing'
    try:
        await supabase_handler.update_image_record(
            task_id=request_data.task_id, # Main client task_id
            image_id=image_db_id,
            status="processing", # Indicates task sent to Celery and being processed
            ai_service_task_id=celery_task.id
        )
        logger.info(f"Updated image record {image_db_id} with Celery task ID {celery_task.id}")
    except Exception as e:
        # Log this error but proceed to return task ID to client, as Celery task is dispatched.
        # The task itself should handle failures gracefully.
        logger.error(f"Failed to update Supabase record {image_db_id} with Celery task ID {celery_task.id}: {e}", exc_info=True)
        # Potentially raise an alert or specific monitoring event here.

    return TaskIdResponse(celery_task_id=celery_task.id)

@router.post("/text-to-image", response_model=TaskIdResponse, include_in_schema=False)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def generate_text_to_image_endpoint(
    request: Request, 
    request_data: TextToImageRequest,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Initiates 2D image generation from text using multiple AI providers."""
    logger.info(f"Received request for /generate/text-to-image for task_id: {request_data.task_id} using provider: {request_data.provider} from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()

    # Validate provider
    if request_data.provider not in ["openai", "stability", "recraft", "flux"]:
        raise HTTPException(status_code=400, detail="text-to-image supports 'openai', 'stability', 'recraft', and 'flux' providers")

    # For text-to-image, we don't need to fetch an input image

    try:
        # Create the record in images table before dispatching the task
        db_record = await supabase_handler.create_image_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style,
            status="pending",
            user_id=user_id_from_auth,
            image_type="ai_generated",
            metadata={"provider": request_data.provider}
        )
        image_db_id = db_record["id"]
        logger.info(f"Created image record {image_db_id} for task {request_data.task_id}")

        logger.info(f"Sending {request_data.provider} text-to-image task to Celery for image_db_id: {image_db_id}")
        
        if request_data.provider == "openai":
            # For OpenAI text-to-image, we don't need image_bytes, so pass empty string
            celery_task = generate_openai_image_task.delay(
                image_db_id,
                "",  # Empty string for text-to-image
                "",  # No filename for text-to-image
                request_data.model_dump()
            )
        elif request_data.provider == "stability":
            celery_task = generate_stability_image_task.delay(
                image_db_id,
                "",  # Empty string for text-to-image
                request_data.model_dump(),
                "text_to_image"
            )
        elif request_data.provider == "recraft":
            celery_task = generate_recraft_image_task.delay(
                image_db_id,
                "",  # Empty string for text-to-image
                request_data.model_dump(),
                "text_to_image"
            )
        elif request_data.provider == "flux":
            celery_task = generate_flux_image_task.delay(
                image_db_id,
                "",  # Empty string for text-to-image
                request_data.model_dump(),
                "text_to_image"
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {request_data.provider}")
            
        logger.info(f"Celery task ID: {celery_task.id} for image_db_id: {image_db_id}")

        # Update the Supabase record with the Celery task ID and set status to 'processing'
        await supabase_handler.update_image_record(
            task_id=request_data.task_id,
            image_id=image_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        logger.info(f"Updated image record {image_db_id} with Celery task ID {celery_task.id}")
        
        return TaskIdResponse(celery_task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /text-to-image endpoint for task {request_data.task_id}: {e}", exc_info=True)
        # Attempt to update status to failed if db_record was created
        if 'image_db_id' in locals() and image_db_id:
            try:
                await supabase_handler.update_image_record(task_id=request_data.task_id, image_id=image_db_id, status="failed")
            except Exception as db_update_e:
                logger.error(f"Failed to update image record to failed: {db_update_e}")
        raise HTTPException(status_code=500, detail=f"Failed to process text-to-image request: {str(e)}")

@router.post("/sketch-to-image", response_model=TaskIdResponse, include_in_schema=False)
async def generate_sketch_to_image_endpoint(
    request: Request, 
    request_data: SketchToImageRequest,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Initiates 2D image generation from a single sketch image (Supabase URL) using Stability AI."""
    logger.info(f"Received request for /generate/sketch-to-image for task_id: {request_data.task_id} from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()

    # Fetch the image from Supabase first
    try:
        image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_sketch_asset_url)
        if not image_bytes:
            raise HTTPException(status_code=404, detail="Failed to fetch input sketch from Supabase for async mode.")
    except HTTPException as e:
        logger.error(f"Failed to fetch input sketch from Supabase for async mode: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching input sketch from Supabase for async mode: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve input sketch from Supabase for asynchronous processing.")

    try:
        # Create the record in images table before dispatching the task
        db_record = await supabase_handler.create_image_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style_preset,
            status="pending",
            user_id=user_id_from_auth,
            image_type="ai_generated"
        )
        image_db_id = db_record["id"]
        logger.info(f"Created image record {image_db_id} for sketch-to-image task {request_data.task_id}")

        # Use Stability image task for sketch-to-image
        celery_task = generate_stability_image_task.delay(
            image_db_id,
            base64.b64encode(image_bytes).decode('utf-8'),
            request_data.model_dump(),
            "sketch_to_image"
        )
        logger.info(f"Celery task ID: {celery_task.id} for image_db_id: {image_db_id}")

        await supabase_handler.update_image_record(
            task_id=request_data.task_id,
            image_id=image_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        logger.info(f"Updated image record {image_db_id} with Celery task ID {celery_task.id}")

        return TaskIdResponse(celery_task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /sketch-to-image endpoint for task {request_data.task_id}: {e}", exc_info=True)
        # Attempt to update status to failed if db_record was created
        if 'image_db_id' in locals() and image_db_id:
            try:
                await supabase_handler.update_image_record(task_id=request_data.task_id, image_id=image_db_id, status="failed")
            except Exception as db_update_e:
                logger.error(f"Failed to update image record to failed: {db_update_e}")
        raise HTTPException(status_code=500, detail=f"Failed to process sketch-to-image request: {str(e)}")

@router.post("/remove-background", response_model=TaskIdResponse)
async def remove_background_endpoint(
    request: Request, 
    request_data: RemoveBackgroundRequest,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Remove background from an image using Stability AI or Recraft."""
    logger.info(f"Received request for /remove-background for task_id: {request_data.task_id} from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()

    # Fetch the image from Supabase first
    try:
        image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
        if not image_bytes:
            raise HTTPException(status_code=404, detail="Failed to fetch input image from Supabase for async mode.")
    except HTTPException as e:
        logger.error(f"Failed to fetch input image from Supabase for async mode: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching input image from Supabase for async mode: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve input image from Supabase for asynchronous processing.")

    try:
        # Create the record in images table before dispatching the task
        db_record = await supabase_handler.create_image_record(
            task_id=request_data.task_id,
            prompt="Remove background",
            style=None,
            status="pending",
            user_id=user_id_from_auth
        )
        image_db_id = db_record["id"]
        logger.info(f"Created image record {image_db_id} for remove-background task {request_data.task_id}")

        if request_data.provider == "stability":
            celery_task = generate_stability_image_task.delay(
                image_db_id,
                base64.b64encode(image_bytes).decode('utf-8'),
                request_data.model_dump(),
                "remove_background"
            )
        elif request_data.provider == "recraft":
            celery_task = generate_recraft_image_task.delay(
                image_db_id,
                base64.b64encode(image_bytes).decode('utf-8'),
                request_data.model_dump(),
                "remove_background"
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider for remove-background: {request_data.provider}")
            
        logger.info(f"Celery task ID: {celery_task.id} for image_db_id: {image_db_id}")

        await supabase_handler.update_image_record(
            task_id=request_data.task_id,
            image_id=image_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        return TaskIdResponse(celery_task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /remove-background endpoint for task {request_data.task_id}: {e}", exc_info=True)
        if 'image_db_id' in locals() and image_db_id:
            try: await supabase_handler.update_image_record(task_id=request_data.task_id, image_id=image_db_id, status="failed")
            except: pass
        raise HTTPException(status_code=500, detail=f"Failed to process remove-background request: {str(e)}")

@router.post("/image-inpaint", response_model=TaskIdResponse, include_in_schema=False)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def image_inpaint_endpoint(
    request: Request, 
    request_data: ImageInpaintRequest,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Inpaints an image using a mask with Recraft AI."""
    logger.info(f"Received request for /image-inpaint for task_id: {request_data.task_id} using provider: {request_data.provider} from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()

    # Validate provider
    if request_data.provider != "recraft":
        raise HTTPException(status_code=400, detail="Only 'recraft' provider is supported for image-inpaint")

    # Fetch the image from Supabase first
    try:
        image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
        mask_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_mask_asset_url)
        logger.info(f"Successfully fetched input image and mask for async Recraft inpaint task {request_data.task_id}")
    except HTTPException as e:
        logger.error(f"Failed to fetch input assets from Supabase for async task {request_data.task_id}: {e.detail}")
        raise HTTPException(status_code=404, detail="Failed to fetch input image or mask from Supabase for asynchronous processing.")

    try:
        # Create the record in images table before dispatching the task
        db_record = await supabase_handler.create_image_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style,
            status="pending",
            user_id=user_id_from_auth
        )
        image_db_id = db_record["id"]
        logger.info(f"Created image record {image_db_id} for image-inpaint task {request_data.task_id}")

        # Use Recraft image task with inpaint operation
        from tasks.generation_image_tasks import generate_recraft_image_task
        
        # We need to pass both image and mask bytes - we'll modify the task to handle this
        # For now, we'll pass the mask bytes in the metadata and handle it in the task
        request_data_with_mask = request_data.model_dump()
        request_data_with_mask["mask_bytes"] = mask_bytes
        
        celery_task = generate_recraft_image_task.delay(
            image_db_id,
            base64.b64encode(image_bytes).decode('utf-8'),
            request_data_with_mask,
            "inpaint"
        )
            
        logger.info(f"Celery task ID: {celery_task.id} for image_db_id: {image_db_id}")

        await supabase_handler.update_image_record(
            task_id=request_data.task_id,
            image_id=image_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        return TaskIdResponse(celery_task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /image-inpaint endpoint for task {request_data.task_id}: {e}", exc_info=True)
        if 'image_db_id' in locals() and image_db_id:
            try: await supabase_handler.update_image_record(task_id=request_data.task_id, image_id=image_db_id, status="failed")
            except: pass
        raise HTTPException(status_code=500, detail=f"Failed to process image-inpaint request: {str(e)}")

@router.post("/search-and-recolor", response_model=TaskIdResponse, include_in_schema=False)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def search_and_recolor_endpoint(
    request: Request, 
    request_data: SearchAndRecolorRequest,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Search for objects in an image and recolor them using Stability AI."""
    operation_id = f"search-recolor-{request_data.task_id}"
    logger.info(f"Received search-and-recolor request for task {request_data.task_id} (Operation ID: {operation_id}) from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()
    
    if request_data.provider != "stability":
        logger.error(f"Invalid provider '{request_data.provider}' for search-and-recolor. Only 'stability' is supported.")
        raise HTTPException(status_code=400, detail="Search-and-recolor is only supported by Stability AI provider.")

    # Fetch the image from Supabase first
    try:
        image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
        logger.info(f"Successfully fetched input image for async search-and-recolor task {operation_id}")
    except HTTPException as e:
        logger.error(f"Failed to fetch input image from Supabase for async task {operation_id}: {e.detail}")
        raise HTTPException(status_code=404, detail="Failed to fetch input image from Supabase for asynchronous processing.")

    try:
        # Create the record in images table before dispatching the task
        db_record = await supabase_handler.create_image_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style_preset,
            status="queued",
            user_id=user_id_from_auth,
            image_type="ai_generated",
            metadata={"async_mode": True, "provider": "stability", "operation": "search_and_recolor"}
        )
        image_db_id = db_record["id"]
        logger.info(f"Created image DB record {image_db_id} for async task {operation_id}")

        # Convert request data to dict for Celery serialization
        request_data_dict = request_data.model_dump()

        # Queue the Celery task
        celery_task = generate_stability_image_task.delay(
            image_db_id, 
            base64.b64encode(image_bytes).decode('utf-8'), 
            request_data_dict, 
            "search_and_recolor"
        )
        celery_task_id = celery_task.id
        logger.info(f"Queued async Stability search-and-recolor task {celery_task_id} for DB record {image_db_id}")

        # Update the DB record with the Celery task ID
        await supabase_handler.update_image_record(
            task_id=request_data.task_id,
            image_id=image_db_id,
            ai_service_task_id=celery_task_id,
            status="queued"
        )
        logger.info(f"Updated image DB record {image_db_id} with Celery task ID {celery_task_id}")

        return TaskIdResponse(celery_task_id=celery_task_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /search-and-recolor endpoint for task {request_data.task_id}: {e}", exc_info=True)
        if 'image_db_id' in locals() and image_db_id:
            try: await supabase_handler.update_image_record(task_id=request_data.task_id, image_id=image_db_id, status="failed")
            except: pass
        raise HTTPException(status_code=500, detail=f"Failed to process search-and-recolor request: {str(e)}")

@router.post("/upscale", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def upscale_endpoint(
    request: Request, 
    request_data: UpscaleRequest,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Upscale an image using Stability AI or Recraft AI."""
    logger.info(f"Received request for /upscale for task_id: {request_data.task_id} using provider: {request_data.provider} from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()

    # Validate provider
    if request_data.provider not in ["stability", "recraft"]:
        raise HTTPException(status_code=400, detail="Upscale supports 'stability' and 'recraft' providers")

    # Fetch the image from Supabase first
    try:
        image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
        logger.info(f"Successfully fetched input image for upscale task {request_data.task_id}")
    except HTTPException as e:
        logger.error(f"Failed to fetch input image from Supabase for upscale task {request_data.task_id}: {e.detail}")
        raise HTTPException(status_code=404, detail="Failed to fetch input image from Supabase for upscale processing.")

    try:
        # Create the record in images table before dispatching the task
        db_record = await supabase_handler.create_image_record(
            task_id=request_data.task_id,
            prompt="Upscale image",
            style=None,
            status="pending",
            user_id=user_id_from_auth,
            image_type="ai_generated",
            metadata={"provider": request_data.provider, "operation": "upscale"}
        )
        image_db_id = db_record["id"]
        logger.info(f"Created image record {image_db_id} for upscale task {request_data.task_id}")

        if request_data.provider == "stability":
            celery_task = generate_stability_image_task.delay(
                image_db_id,
                base64.b64encode(image_bytes).decode('utf-8'),
                request_data.model_dump(),
                "upscale"
            )
        elif request_data.provider == "recraft":
            celery_task = generate_recraft_image_task.delay(
                image_db_id,
                base64.b64encode(image_bytes).decode('utf-8'),
                request_data.model_dump(),
                "upscale"
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider for upscale: {request_data.provider}")
            
        logger.info(f"Celery task ID: {celery_task.id} for image_db_id: {image_db_id}")

        await supabase_handler.update_image_record(
            task_id=request_data.task_id,
            image_id=image_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        return TaskIdResponse(celery_task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /upscale endpoint for task {request_data.task_id}: {e}", exc_info=True)
        if 'image_db_id' in locals() and image_db_id:
            try: await supabase_handler.update_image_record(task_id=request_data.task_id, image_id=image_db_id, status="failed")
            except: pass
        raise HTTPException(status_code=500, detail=f"Failed to process upscale request: {str(e)}")

@router.post("/downscale", response_model=TaskIdResponse)
@limiter.limit("30/minute")  # More permissive rate limit for basic image processing
async def downscale_endpoint(
    request: Request,
    request_data: DownscaleRequest,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Downscale images to specified file size with aspect ratio control using basic image processing."""
    logger.info(f"Received request for /generate/downscale for task_id: {request_data.task_id} from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()
    
    # Fetch the image from Supabase first
    try:
        image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
        logger.info(f"Successfully fetched input image for task {request_data.task_id} from: {request_data.input_image_asset_url}")
        
        # Validate file size (max 20MB)
        image_size_mb = len(image_bytes) / (1024 * 1024)
        if image_size_mb > 20.0:
            raise HTTPException(
                status_code=413, 
                detail=f"Input image size ({image_size_mb:.1f}MB) exceeds maximum allowed size (20MB)"
            )
        
        # Check if image is already smaller than target
        if image_size_mb <= request_data.max_size_mb:
            logger.info(f"Input image ({image_size_mb:.2f}MB) is already smaller than target ({request_data.max_size_mb}MB)")
            # Don't reject - still process for potential square padding and format conversion
        
    except HTTPException as e:
        logger.error(f"Failed to fetch image from Supabase for task {request_data.task_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching image for task {request_data.task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve input image.")
    
    try:
        # Create the record in images table before dispatching the task
        db_record = await supabase_handler.create_image_record(
            task_id=request_data.task_id,
            prompt=f"Downscale to {request_data.max_size_mb}MB ({request_data.aspect_ratio_mode})",
            style=None,  # Don't use a computed style that might violate DB constraints
            status="pending",
            user_id=user_id_from_auth,
            image_type="upload",  # This is processing an uploaded/existing image
            metadata={
                "processing_type": "downscale",
                "target_size_mb": request_data.max_size_mb,
                "aspect_ratio_mode": request_data.aspect_ratio_mode,
                "output_format": request_data.output_format,
                "original_size_mb": round(image_size_mb, 2)
            }
        )
        image_db_id = db_record["id"]
        logger.info(f"Created image record {image_db_id} for task {request_data.task_id}")
    except HTTPException as e:
        logger.error(f"Failed to create Supabase record for task {request_data.task_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating Supabase record for task {request_data.task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize task record.")
    
    logger.info(f"Sending downscale task to Celery for db_id: {image_db_id}")
    
    # Dispatch Celery task
    celery_task = generate_downscale_image_task.delay(
        image_db_id,
        base64.b64encode(image_bytes).decode('utf-8'),
        request_data.model_dump()
    )
    
    logger.info(f"Celery task ID: {celery_task.id} for image_db_id: {image_db_id}")
    
    # Update the Supabase record with the Celery task ID and set status to 'processing'
    try:
        await supabase_handler.update_image_record(
            task_id=request_data.task_id,
            image_id=image_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        logger.info(f"Updated image record {image_db_id} with Celery task ID {celery_task.id}")
    except Exception as e:
        logger.error(f"Failed to update Supabase record {image_db_id} with Celery task ID {celery_task.id}: {e}", exc_info=True)
    
    return TaskIdResponse(celery_task_id=celery_task.id)

# The /select-concept endpoint and its associated Celery task import have been removed.
# The SelectConceptRequest schema import is also removed from app.schemas.generation_schemas. 