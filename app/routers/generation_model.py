import httpx
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request, Depends
from typing import List, Optional
import logging
import base64
import uuid
import time

# Import authentication
from auth import get_current_tenant, TenantContext

# Test user ID for endpoints when auth is not implemented (kept for backward compatibility)
TEST_USER_ID = "00000000-0000-4000-8000-000000000001"

# Explicitly import required schemas from the module (model-related only)
from schemas.generation_schemas import (
    TextToModelRequest,
    ImageToModelRequest,
    RefineModelRequest,
    TaskIdResponse,
)

# Import configuration and dependencies
from config import settings # Import settings
from limiter import limiter # Import the limiter

import supabase_handler # New Supabase handler

# Import only model-related tasks
from tasks.generation_model_tasks import (
    generate_tripo_text_to_model_task,
    generate_tripo_image_to_model_task,
    generate_tripo_refine_model_task,
    generate_stability_model_task,
    generate_tripoai_model_task
)

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/text-to-model", response_model=TaskIdResponse, include_in_schema=False)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def generate_text_to_model_endpoint(
    request: Request, # FastAPI request object for context if needed (e.g., user)
    request_data: TextToModelRequest, # Updated to use Pydantic model from request body
    tenant: TenantContext = Depends(get_current_tenant) # Authentication dependency
):
    """Initiates 3D model generation from text using multiple AI providers."""
    # Generate task_id (server-managed, never client-provided)
    task_id = f"text-to-model-{int(time.time())}-{str(uuid.uuid4())[:8]}"
    
    logger.info(f"Received request for /generate/text-to-model for task_id: {task_id} using provider: {request_data.provider} from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()

    # Validate provider
    if request_data.provider not in ["tripoai"]:
        raise HTTPException(status_code=400, detail="text-to-model currently supports only 'tripoai' provider")

    try:
        # Create the record in models table before dispatching the task
        db_record = await supabase_handler.create_model_record(
            task_id=task_id,
            prompt=request_data.prompt,
            status="pending",
            user_id=user_id_from_auth,
            model_type="ai_generated",
            metadata={"provider": request_data.provider, "async_mode": True}
        )
        model_db_id = db_record["id"]
        logger.info(f"Created model record {model_db_id} for task {task_id}")

        logger.info(f"Sending {request_data.provider} text-to-model task to Celery for model_db_id: {model_db_id}")
        
        # Dispatch to TripoAI task
        celery_task = generate_tripoai_model_task.delay(
            model_db_id,
            "",  # No image_bytes for text-to-model
            request_data.model_dump(),
            "text_to_model"
        )
            
        logger.info(f"Celery task ID: {celery_task.id} for model_db_id: {model_db_id}")

        # Update the Supabase record with the Celery task ID and set status to 'processing'
        await supabase_handler.update_model_record(
            task_id=task_id,
            model_id=model_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        logger.info(f"Updated model record {model_db_id} with Celery task ID {celery_task.id}")
        
        return TaskIdResponse(task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /text-to-model endpoint for task {task_id}: {e}", exc_info=True)
        # Attempt to update status to failed if db_record was created
        if 'model_db_id' in locals() and model_db_id:
            try:
                await supabase_handler.update_model_record(task_id=task_id, model_id=model_db_id, status="failed")
            except Exception as db_update_e:
                logger.error(f"Failed to update model record to failed: {db_update_e}")
        raise HTTPException(status_code=500, detail=f"Failed to process text-to-model request: {str(e)}")

@router.post("/image-to-model", response_model=TaskIdResponse, include_in_schema=False)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def generate_image_to_model_endpoint(
    request: Request, 
    request_data: ImageToModelRequest,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Initiates 3D model generation from an image using multiple AI providers."""
    # Generate task_id (server-managed, never client-provided)
    task_id = f"image-to-model-{int(time.time())}-{str(uuid.uuid4())[:8]}"
    
    logger.info(f"Received request for /generate/image-to-model for task_id: {task_id} using provider: {request_data.provider} from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()

    # Validate provider
    if request_data.provider not in ["tripoai"]:
        raise HTTPException(status_code=400, detail="image-to-model currently supports only 'tripoai' provider")

    # Fetch the image from Supabase first
    try:
        image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
        logger.info(f"Successfully fetched input image for task {task_id} from: {request_data.input_image_asset_url}")
    except HTTPException as e:
        logger.error(f"Failed to fetch image from Supabase for task {task_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching image for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve input image.")

    try:
        # Create the record in models table before dispatching the task
        db_record = await supabase_handler.create_model_record(
            task_id=task_id,
            prompt=request_data.prompt,
            status="pending",
            user_id=user_id_from_auth,
            model_type="ai_generated",
            metadata={"provider": request_data.provider, "async_mode": True}
        )
        model_db_id = db_record["id"]
        logger.info(f"Created model record {model_db_id} for task {task_id}")

        logger.info(f"Sending {request_data.provider} image-to-model task to Celery for model_db_id: {model_db_id}")
        
        # Dispatch to TripoAI task
        celery_task = generate_tripoai_model_task.delay(
            model_db_id,
            base64.b64encode(image_bytes).decode('utf-8'),
            request_data.model_dump(),
            "image_to_model"
        )
            
        logger.info(f"Celery task ID: {celery_task.id} for model_db_id: {model_db_id}")

        # Update the Supabase record with the Celery task ID and set status to 'processing'
        await supabase_handler.update_model_record(
            task_id=task_id,
            model_id=model_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        logger.info(f"Updated model record {model_db_id} with Celery task ID {celery_task.id}")
        
        return TaskIdResponse(task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /image-to-model endpoint for task {task_id}: {e}", exc_info=True)
        # Attempt to update status to failed if db_record was created
        if 'model_db_id' in locals() and model_db_id:
            try:
                await supabase_handler.update_model_record(task_id=task_id, model_id=model_db_id, status="failed")
            except Exception as db_update_e:
                logger.error(f"Failed to update model record to failed: {db_update_e}")
        raise HTTPException(status_code=500, detail=f"Failed to process image-to-model request: {str(e)}")

@router.post("/refine-model", response_model=TaskIdResponse, include_in_schema=False)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def refine_model_endpoint(
    request: Request, 
    request_data: RefineModelRequest,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Refines an existing 3D model using multiple AI providers."""
    # Generate task_id (server-managed, never client-provided)
    task_id = f"refine-model-{int(time.time())}-{str(uuid.uuid4())[:8]}"
    
    logger.info(f"Received request for /generate/refine-model for task_id: {task_id} using provider: {request_data.provider} from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()

    # Validate provider
    if request_data.provider not in ["tripoai"]:
        raise HTTPException(status_code=400, detail="refine-model currently supports only 'tripoai' provider")

    # Fetch the model file from Supabase first
    try:
        model_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_model_asset_url)
        logger.info(f"Successfully fetched input model for task {task_id} from: {request_data.input_model_asset_url}")
    except HTTPException as e:
        logger.error(f"Failed to fetch model from Supabase for task {task_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching model for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve input model.")

    try:
        # Create the record in models table before dispatching the task
        db_record = await supabase_handler.create_model_record(
            task_id=task_id,
            prompt=request_data.prompt,
            status="pending",
            user_id=user_id_from_auth,
            model_type="ai_refined",
            metadata={"provider": request_data.provider, "async_mode": True, "operation": "refine"}
        )
        model_db_id = db_record["id"]
        logger.info(f"Created model record {model_db_id} for task {task_id}")

        logger.info(f"Sending {request_data.provider} refine-model task to Celery for model_db_id: {model_db_id}")
        
        # Dispatch to TripoAI task with model bytes
        celery_task = generate_tripoai_model_task.delay(
            model_db_id,
            base64.b64encode(model_bytes).decode('utf-8'),
            request_data.model_dump(),
            "refine_model"
        )
            
        logger.info(f"Celery task ID: {celery_task.id} for model_db_id: {model_db_id}")

        # Update the Supabase record with the Celery task ID and set status to 'processing'
        await supabase_handler.update_model_record(
            task_id=task_id,
            model_id=model_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        logger.info(f"Updated model record {model_db_id} with Celery task ID {celery_task.id}")
        
        return TaskIdResponse(task_id=celery_task.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /refine-model endpoint for task {task_id}: {e}", exc_info=True)
        # Attempt to update status to failed if db_record was created
        if 'model_db_id' in locals() and model_db_id:
            try:
                await supabase_handler.update_model_record(task_id=task_id, model_id=model_db_id, status="failed")
            except Exception as db_update_e:
                logger.error(f"Failed to update model record to failed: {db_update_e}")
        raise HTTPException(status_code=500, detail=f"Failed to process refine-model request: {str(e)}") 