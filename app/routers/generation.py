import httpx
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from typing import List, Optional
import logging
# import uuid # Removed as Celery will generate task IDs
import uuid # Import uuid for synchronous mode
import base64 # Import base64 for synchronous mode

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

# Import client functions for synchronous mode
from app.ai_clients import openai_client
from app.supabase_client import upload_image_to_storage, create_concept_image_record
from app.config import settings # Import settings
from app.sync_state import sync_task_results # Import the synchronous task results store from the new module

# from app.routers.models import task_store # Removed in-memory store
# Removed import of app.routers.models to break circular dependency

from app.tasks.generation_tasks import (
    generate_openai_image_task, # Keep import for type hinting or potential future use
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

    if settings.sync_mode:
        logger.info("Running OpenAI image generation task synchronously.")
        # Generate a dummy task ID for the synchronous run
        task_id = str(uuid.uuid4())

        try:
            # --- OpenAI API Call (Synchronous) ---
            # Call the core logic that was in the Celery task
            # Need to pass a dummy 'self' or refactor the task logic
            # For simplicity, I'll duplicate the core logic here
            openai_response = await openai_client.generate_image_to_image(
                image_bytes, image.filename, request_data
            )

            b64_images = [item["b64_json"] for item in openai_response.get("data", [])]

            logger.info(f"Synchronous task {task_id}: OpenAI image generation completed, processing {len(b64_images)} images.")

            # --- Supabase Upload and Database Record and URL Construction (Synchronous) ---
            uploaded_image_download_urls = []
            bucket_name = "concept-images" # Define the bucket name
            for i, b64_image in enumerate(b64_images):
                try:
                    image_data = base64.b64decode(b64_image)
                    file_name = f"{task_id}/{i}.png"
                    file_path = await upload_image_to_storage(file_name, image_data, bucket_name)
                    download_url = f"{settings.bff_base_url}/images/{bucket_name}/{file_path}"
                    uploaded_image_download_urls.append(download_url)
                    await create_concept_image_record(task_id, download_url, bucket_name, request_data.prompt, request_data.style)
                    logger.info(f"Synchronous task {task_id}: Processed and uploaded image {i}.")
                except Exception as upload_e:
                    logger.error(f"Synchronous task {task_id}: Failed to process and upload image {i}: {upload_e}", exc_info=True)
                    pass # Continue processing other images

            if not uploaded_image_download_urls:
                 raise HTTPException(status_code=500, detail="No images were successfully processed and uploaded in synchronous mode.")

            logger.info(f"Synchronous task {task_id}: Finished processing and uploading images.")

            # Store the result in the in-memory store for synchronous tasks
            sync_task_results[task_id] = {'image_urls': uploaded_image_download_urls}
            logger.info(f"Synchronous task {task_id}: Stored result in in-memory store.")

            # Return a response mimicking the task status endpoint's successful result
            # The test's poll_task_status will need to be adapted slightly or we return a different response structure
            # For the current test structure expecting poll_task_status return, let's return a TaskIdResponse
            # The test will then need to hit the status endpoint which can handle the synchronous task ID.

            # NOTE: The current test setup polls the status endpoint based on the initial response task_id.
            # To make the synchronous flow work with the existing test polling logic:
            # The /tasks/{task_id}/status endpoint needs to be aware of synchronous task IDs
            # and directly return the result when polled, instead of querying Celery state.
            # This requires modifying the /tasks/{task_id}/status endpoint.

            # For now, I'll modify the endpoint to return the task_id as before.
            # We will need to update the /tasks/{task_id}/status endpoint next.

            return TaskIdResponse(task_id=task_id)

        except Exception as e:
            logger.error(f"Synchronous OpenAI task failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Synchronous OpenAI task failed: {e}")

    else:
        # Original logic: Send task to Celery
        logger.info("Sending OpenAI image generation task to Celery...")
        task = generate_openai_image_task.delay(
            image_bytes,
            image.filename,
            request_data.model_dump()
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