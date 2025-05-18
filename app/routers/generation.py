import httpx
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from typing import List, Optional
import logging
# import uuid # Removed as Celery will generate task IDs
# import asyncio # Removed as Celery handles background tasks

# Explicitly import required schemas from the module
from app.schemas.generation_schemas import (
    ImageToImageRequest,
    TextToModelRequest,
    ImageToModelRequest,
    SketchToModelRequest,
    RefineModelRequest,
    TaskIdResponse,
    ImageToImageResponse,
    SelectConceptRequest
)

# from app.routers.models import task_store # Removed in-memory store
from app.tasks.generation_tasks import (
    generate_openai_image_task,
    generate_tripo_text_to_model_task,
    generate_tripo_image_to_model_task,
    generate_tripo_sketch_to_model_task,
    generate_tripo_refine_model_task,
    generate_tripo_select_concept_task
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Removed run_openai_image_task as it's now a Celery task

@router.post("/image-to-image", response_model=TaskIdResponse)
async def generate_image_to_image_endpoint(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    style: Optional[str] = Form(None),
    n: Optional[int] = Form(1)
):
    """Generates 2D concepts from an input image and text prompt using OpenAI.
    Handles multipart/form-data for the image file.
    """
    logger.info(f"Received request for /generate/image-to-image with n={n}")
    # Read image file content
    image_bytes = await image.read()

    # Prepare data for client (excluding file which is handled separately)
    request_data = ImageToImageRequest(prompt=prompt, style=style, n=n)

    # Send task to Celery and return the task ID
    logger.info("Sending OpenAI image generation task to Celery...")
    # Serialize request_data to dictionary for Celery
    task = generate_openai_image_task.delay(
        image_bytes,
        image.filename,
        request_data.model_dump() # Pass Pydantic model as dict
    )

    logger.info(f"Celery task ID: {task.id}")
    return TaskIdResponse(task_id=task.id)

@router.post("/text-to-model", response_model=TaskIdResponse)
async def generate_text_to_model_endpoint(request_data: TextToModelRequest):
    """Initiates 3D model generation from text using Tripo AI."""
    logger.info("Received request for /generate/text-to-model")
    # Send task to Celery and return the task ID
    logger.info("Sending Tripo AI text-to-model task to Celery...")
    task = generate_tripo_text_to_model_task.delay(request_data.model_dump())
    logger.info(f"Celery task ID: {task.id}")
    return TaskIdResponse(task_id=task.id)

@router.post("/image-to-model", response_model=TaskIdResponse)
async def generate_image_to_model_endpoint(request_data: ImageToModelRequest):
    """Initiates 3D model generation from multiple images (multiview) using Tripo AI."""
    logger.info("Received request for /generate/image-to-model (multiview)")
    # Send task to Celery and return the task ID
    logger.info("Sending Tripo AI image-to-model task to Celery...")
    task = generate_tripo_image_to_model_task.delay(request_data.model_dump())
    logger.info(f"Celery task ID: {task.id}")
    return TaskIdResponse(task_id=task.id)

@router.post("/sketch-to-model", response_model=TaskIdResponse)
async def generate_sketch_to_model_endpoint(request_data: SketchToModelRequest):
    """Initiates 3D model generation from a single sketch image using Tripo AI."""
    logger.info("Received request for /generate/sketch-to-model")
    # Send task to Celery and return the task ID
    logger.info("Sending Tripo AI sketch-to-model task to Celery...")
    task = generate_tripo_sketch_to_model_task.delay(request_data.model_dump())
    logger.info(f"Celery task ID: {task.id}")
    return TaskIdResponse(task_id=task.id)

@router.post("/refine-model", response_model=TaskIdResponse)
async def refine_model_endpoint(request_data: RefineModelRequest):
    """Initiates refinement of a 3D model using Tripo AI."""
    logger.info("Received request for /generate/refine-model")
    # Send task to Celery and return the task ID
    logger.info("Sending Tripo AI refine-model task to Celery...")
    task = generate_tripo_refine_model_task.delay(request_data.model_dump())
    logger.info(f"Celery task ID: {task.id}")
    return TaskIdResponse(task_id=task.id)

@router.post("/select-concept", response_model=TaskIdResponse)
async def select_concept_endpoint(request_data: SelectConceptRequest):
    """Handles selection of a 2D concept and initiates 3D generation from it using Tripo AI."""
    logger.info("Received request for /generate/select-concept")
    # Send task to Celery and return the task ID
    logger.info("Sending Tripo AI select-concept task to Celery...")
    task = generate_tripo_select_concept_task.delay(request_data.model_dump())
    logger.info(f"Celery task ID: {task.id}")
    return TaskIdResponse(task_id=task.id) 