import httpx
from fastapi import APIRouter, HTTPException, Request, Depends
import logging
import uuid
import time

# Import authentication
from auth import get_current_tenant, TenantContext

# Import required schemas
from schemas.generation_schemas import (
    VideoGenerationRequest,
    TaskIdResponse,
)

# Import video generation task
from tasks.generation_video_tasks import generate_video_task

from config import settings  # Import settings
from limiter import limiter  # Import the limiter

import supabase_handler  # Supabase handler

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/video", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def generate_video_endpoint(
    request: Request,
    request_data: VideoGenerationRequest,
    tenant: TenantContext = Depends(get_current_tenant)
):
    """Initiates video generation from text or image using multiple AI providers."""
    task_id_prefix = "image-to-video" if request_data.start_image else "text-to-video"
    task_id = f"{task_id_prefix}-{int(time.time())}-{str(uuid.uuid4())[:8]}"
    
    logger.info(f"Received request for /generate/video for task_id: {task_id} from tenant: {tenant.tenant_id}")
    user_id_from_auth = tenant.get_user_id()

    # Determine operation key based on request parameters
    operation_type = "image_to_video" if request_data.start_image else "text_to_video"
    operation_key = f"{operation_type}_{request_data.provider}_{request_data.model}_{request_data.mode}_{request_data.duration}s"
    
    # Check and deduct credits before starting generation
    try:
        if user_id_from_auth:  # Only deduct credits for authenticated users
            credit_result = await supabase_handler.check_and_deduct_credits(
                user_id=user_id_from_auth,
                operation_key=operation_key,
                task_id=task_id
            )
            logger.info(f"Credits deducted for task {task_id}: {credit_result['credits_deducted']} credits, remaining: {credit_result['remaining_credits']}")
    except HTTPException as e:
        logger.error(f"Credit check failed for task {task_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during credit check for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process payment.")

    try:
        db_record = await supabase_handler.create_video_record(
            task_id=task_id,
            prompt=request_data.prompt,
            style=f"{request_data.mode}-{request_data.duration}s",
            status="pending",
            user_id=user_id_from_auth,
            metadata=request_data.model_dump()
        )
        video_db_id = db_record["id"]
        logger.info(f"Created video record {video_db_id} for task {task_id}")

        # Add task_id to request data for the Celery task
        request_data_with_task_id = request_data.model_dump()
        request_data_with_task_id["task_id"] = task_id
        
        celery_task = generate_video_task.delay(
            video_db_id=video_db_id,
            request_data_dict=request_data_with_task_id
        )
        logger.info(f"Dispatched Celery task {celery_task.id} for video record {video_db_id}")

        await supabase_handler.update_video_record(
            task_id=task_id,
            video_id=video_db_id,
            status="processing",
            ai_service_task_id=celery_task.id
        )
        return TaskIdResponse(task_id=celery_task.id)

    except Exception as e:
        logger.error(f"Failed to process video generation request for task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initiate video generation.")
