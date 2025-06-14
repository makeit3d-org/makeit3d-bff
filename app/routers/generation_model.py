import httpx
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request
from typing import List, Optional
import logging

# Test user ID for endpoints when auth is not implemented
TEST_USER_ID = "00000000-0000-4000-8000-000000000001"

# Explicitly import required schemas from the module (model-related only)
from app.schemas.generation_schemas import (
    TextToModelRequest,
    ImageToModelRequest,
    RefineModelRequest,
    TaskIdResponse,
)

# Import configuration and dependencies
from app.config import settings # Import settings
from app.limiter import limiter # Import the limiter

import app.supabase_handler as supabase_handler # New Supabase handler

# Import only model-related tasks
from app.tasks.generation_model_tasks import (
    generate_tripo_text_to_model_task,
    generate_tripo_image_to_model_task,
    generate_tripo_refine_model_task,
    generate_stability_model_task
)

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/text-to-model", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_TRIPO_OTHER_REQUESTS_PER_MINUTE}/minute")
async def generate_text_to_model_endpoint(request: Request, request_data: TextToModelRequest):
    """Initiates 3D model generation from text using Tripo AI."""
    logger.info(f"Received request for /generate/text-to-model for task_id: {request_data.task_id} using provider: {request_data.provider}")
    user_id_from_auth = TEST_USER_ID

    # Validate provider
    if request_data.provider != "tripo":
        raise HTTPException(status_code=400, detail="text-to-model only supports 'tripo' provider")

    try:
        # Create the record in models table before dispatching the task
        db_record = await supabase_handler.create_model_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style,
            status="pending",
            user_id=user_id_from_auth,
            metadata={"provider": request_data.provider}
        )
        model_db_id = db_record["id"]
        logger.info(f"Created model record {model_db_id} for task {request_data.task_id}")

        logger.info(f"Sending Tripo text-to-model task to Celery for model_db_id: {model_db_id}")
        
        celery_task = generate_tripo_text_to_model_task.delay(
            model_db_id,
            request_data.model_dump()
        )

        # Update the record with the Celery task ID
        await supabase_handler.update_model_record(
            task_id=request_data.task_id,
            model_id=model_db_id,
            celery_task_id=celery_task.id,
            status="processing"
        )

        logger.info(f"Dispatched Tripo text-to-model Celery task {celery_task.id} for model_db_id: {model_db_id}")
        return TaskIdResponse(celery_task_id=celery_task.id)

    except Exception as e:
        logger.error(f"Failed to dispatch Tripo text-to-model task for {request_data.task_id}: {e}", exc_info=True)
        # Attempt to update DB record to failed if possible
        if 'model_db_id' in locals() and model_db_id:
            try:
                await supabase_handler.update_model_record(task_id=request_data.task_id, model_id=model_db_id, status="failed")
            except Exception as db_update_e:
                logger.error(f"Failed to update model record to failed: {db_update_e}")
        raise HTTPException(status_code=500, detail=f"Failed to dispatch Tripo text-to-model task: {str(e)}")

@router.post("/image-to-model", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_TRIPO_OTHER_REQUESTS_PER_MINUTE}/minute")
async def generate_image_to_model_endpoint(request: Request, request_data: ImageToModelRequest):
    """Initiates 3D model generation from multiple images (Supabase URLs) using multiple AI providers."""
    logger.info(f"Received request for /generate/image-to-model for task_id: {request_data.task_id} using provider: {request_data.provider}")
    user_id_from_auth = TEST_USER_ID

    try:
        # Fetch input images
        image_bytes_list = []
        original_filenames = []
        for url in request_data.input_image_asset_urls:
            try:
                img_bytes, original_filename = await supabase_handler.fetch_asset_from_storage(url)
                image_bytes_list.append(img_bytes)
                original_filenames.append(original_filename or url.split('/')[-1])
            except HTTPException as e:
                logger.error(f"Failed to fetch image {url} for task {request_data.task_id}: {e.detail}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error fetching image {url} for task {request_data.task_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to retrieve input image: {url}")

        if not image_bytes_list:
             raise HTTPException(status_code=400, detail="No input images could be fetched for Celery task.")

        db_record = await supabase_handler.create_model_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style,
            status="pending",
            user_id=user_id_from_auth,
            source_image_id=None,  # No image in direct image-to-model workflow
            metadata={"provider": request_data.provider, **request_data.model_dump(include={"texture", "pbr", "model_version", "face_limit", "auto_size", "texture_quality", "orientation", "texture_resolution", "remesh", "foreground_ratio", "target_type", "target_count", "guidance_scale", "seed"})}
            # Note: source_input_asset_id could be used to track input assets if we create input_assets records
        )
        model_db_id = db_record["id"]
        logger.info(f"Created model record {model_db_id} for image-to-model task {request_data.task_id}")

        logger.info(f"Sending {request_data.provider} image-to-model task to Celery for model_db_id: {model_db_id}")
        
        if request_data.provider == "tripo":
            celery_task = generate_tripo_image_to_model_task.delay(
                model_db_id,
                image_bytes_list,
                original_filenames,
                request_data.model_dump()
            )
        elif request_data.provider == "stability":
            celery_task = generate_stability_model_task.delay(
                model_db_id,
                image_bytes_list[0],  # Use first image for Stability
                request_data.model_dump()
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider for image-to-model: {request_data.provider}")
            
        logger.info(f"Celery task ID: {celery_task.id} for model_db_id: {model_db_id}")

        await supabase_handler.update_model_record(
            task_id=request_data.task_id,
            model_id=model_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        return TaskIdResponse(celery_task_id=celery_task.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /image-to-model endpoint for task {request_data.task_id}: {e}", exc_info=True)
        if 'model_db_id' in locals() and model_db_id:
            try:
                await supabase_handler.update_model_record(task_id=request_data.task_id, model_id=model_db_id, status="failed")
            except: pass # best effort
        raise HTTPException(status_code=500, detail=f"Failed to process image-to-model request: {str(e)}")

@router.post("/refine-model", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_TRIPO_OTHER_REQUESTS_PER_MINUTE}/minute")
async def refine_model_endpoint(request: Request, request_data: RefineModelRequest):
    """Refines an existing 3D model using Tripo AI."""
    logger.info(f"Received request for /refine-model for task_id: {request_data.task_id} using provider: {request_data.provider}")
    user_id_from_auth = TEST_USER_ID

    # Validate provider
    if request_data.provider != "tripo":
        raise HTTPException(status_code=400, detail="refine-model only supports 'tripo' provider")

    try:
        # Fetch the input model from Supabase
        model_bytes, original_filename = await supabase_handler.fetch_asset_from_storage(request_data.input_model_asset_url)
        
        # Create the record in models table before dispatching the task
        db_record = await supabase_handler.create_model_record(
            task_id=request_data.task_id,
            prompt=request_data.prompt,
            style=request_data.style,
            status="pending",
            user_id=user_id_from_auth,
            metadata={"provider": request_data.provider, "operation": "refine"}
        )
        model_db_id = db_record["id"]
        logger.info(f"Created model record {model_db_id} for refine-model task {request_data.task_id}")

        logger.info(f"Sending Tripo refine-model task to Celery for model_db_id: {model_db_id}")
        
        celery_task = generate_tripo_refine_model_task.delay(
            model_db_id,
            model_bytes,
            original_filename,
            request_data.model_dump()
        )
            
        logger.info(f"Celery task ID: {celery_task.id} for model_db_id: {model_db_id}")

        await supabase_handler.update_model_record(
            task_id=request_data.task_id,
            model_id=model_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        return TaskIdResponse(celery_task_id=celery_task.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /refine-model endpoint for task {request_data.task_id}: {e}", exc_info=True)
        if 'model_db_id' in locals() and model_db_id:
            try:
                await supabase_handler.update_model_record(task_id=request_data.task_id, model_id=model_db_id, status="failed")
            except: pass
        raise HTTPException(status_code=500, detail=f"Failed to process refine-model request: {str(e)}") 