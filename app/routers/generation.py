import httpx
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request
from typing import List, Optional
import logging
# import uuid # Removed as Celery will generate task IDs
import uuid # Import uuid for synchronous mode
import base64 # Import base64 for synchronous mode

# Test user ID for endpoints when auth is not implemented
TEST_USER_ID = "00000000-0000-4000-8000-000000000001"

# Explicitly import required schemas from the module
from app.schemas.generation_schemas import (
    ImageToImageRequest,
    TextToModelRequest,
    ImageToModelRequest,
    SketchToModelRequest,
    RefineModelRequest,
    TaskIdResponse,
    # ImageToImageResponse, # This specific response model might change or be incorporated into TaskStatusResponse
    # SelectConceptRequest schema is removed
)

# Import client functions for synchronous mode
from app.ai_clients import openai_client
# from app.supabase_client import upload_image_to_storage, create_concept_image_record # Old supabase client, replaced by handler
from app.config import settings # Import settings
from app.sync_state import sync_task_results # Import the synchronous task results store from the new module
from app.limiter import limiter # Import the limiter

import app.supabase_handler as supabase_handler # New Supabase handler

# from app.routers.models import task_store # Removed in-memory store
# Removed import of app.routers.models to break circular dependency

from app.tasks.generation_tasks import (
    generate_openai_image_task, # Keep import for type hinting or potential future use
    generate_tripo_text_to_model_task,
    generate_tripo_image_to_model_task,
    generate_tripo_sketch_to_model_task,
    generate_tripo_refine_model_task,
    # generate_tripo_select_concept_task is removed
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Removed run_openai_image_task as it's now a Celery task

@router.post("/image-to-image", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_OPENAI_REQUESTS_PER_MINUTE}/minute")
async def generate_image_to_image_endpoint(
    request: Request, # FastAPI request object for context if needed (e.g., user)
    request_data: ImageToImageRequest # Updated to use Pydantic model from request body
):
    """Initiates concept image generation from an input image using OpenAI."""
    logger.info(f"Received request for /generate/image-to-image for task_id: {request_data.task_id}")
    user_id_from_auth = TEST_USER_ID

    if settings.sync_mode:
        logger.info(f"Running OpenAI image-to-image task synchronously for client task_id: {request_data.task_id}.")
        operation_id = str(uuid.uuid4())
        try:
            # Fetch the image from Supabase
            try:
                image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_image_asset_url)
                logger.info(f"Successfully fetched input image for sync OpenAI task {operation_id} from: {request_data.input_image_asset_url}")
            except HTTPException as e:
                logger.error(f"Failed to fetch input image from Supabase for sync task {operation_id}: {e.detail}")
                raise HTTPException(status_code=404, detail="Failed to fetch input image from Supabase for synchronous mode.")

            # Create a DB record for tracking
            sync_db_record = await supabase_handler.create_concept_image_record(
                task_id=request_data.task_id,
                prompt=request_data.prompt,
                style=request_data.style,
                status="processing", # Custom status for sync mode
                user_id=user_id_from_auth,
                ai_service_task_id=operation_id,
                metadata={"sync_mode": True, "background": request_data.background}
            )
            concept_image_db_id = sync_db_record["id"]

            # Call OpenAI directly (synchronous)
            logger.info(f"Sync task {operation_id}: Calling OpenAI API directly.")
            openai_response = await openai_client.generate_image_to_image(
                image_file=image_bytes,
                filename=request_data.input_image_asset_url.split('/')[-1],
                request_data=request_data
            )

            # Extract images from OpenAI response
            b64_images = []
            if "data" in openai_response:
                for img_obj in openai_response["data"]:
                    if "b64_json" in img_obj:
                        b64_images.append(img_obj["b64_json"])

            if not b64_images:
                logger.error(f"Sync task {operation_id}: OpenAI returned no images.")
                await supabase_handler.update_concept_image_record(task_id=request_data.task_id, concept_image_id=concept_image_db_id, status="failed")
                raise HTTPException(status_code=500, detail="OpenAI did not return any images in synchronous mode.")

            logger.info(f"Sync task {operation_id} for client task {request_data.task_id}: OpenAI complete, processing {len(b64_images)} images.")

            # Upload images to Supabase
            uploaded_urls = []
            for i, b64_image in enumerate(b64_images):
                try:
                    # Decode base64 image
                    image_data = base64.b64decode(b64_image)

                    # Upload to Supabase Storage
                    supabase_url = await supabase_handler.upload_asset_to_storage(
                        task_id=request_data.task_id,
                        asset_type_plural="concepts",
                        file_name=f"{i}.png",
                        asset_data=image_data,
                        content_type="image/png"
                    )
                    uploaded_urls.append(supabase_url)
                    logger.info(f"Sync task {operation_id}: Uploaded image {i} to: {supabase_url}")
                except Exception as upload_e:
                    logger.error(f"Sync task {operation_id}: Failed to upload image {i}: {upload_e}", exc_info=True)

            # Update DB record with the first uploaded URL and complete status
            if uploaded_urls:
                await supabase_handler.update_concept_image_record(
                    task_id=request_data.task_id,
                    concept_image_id=concept_image_db_id,
                    asset_url=uploaded_urls[0],
                    status="complete",
                    ai_service_task_id=operation_id,
                    prompt=request_data.prompt,
                    style=request_data.style,
                    metadata={"sync_mode": True, "total_images": len(uploaded_urls)}
                )

                # Store result for polling endpoint
                sync_task_results[operation_id] = {
                    "status": "complete",
                    "result": {"image_urls": uploaded_urls}
                }
                logger.info(f"Sync task {operation_id}: Stored result with {len(uploaded_urls)} URLs. Returning this as task_id for polling.")
                return TaskIdResponse(celery_task_id=operation_id)
            else:
                logger.error(f"Sync task {operation_id}: Failed to upload any images to Supabase.")
                await supabase_handler.update_concept_image_record(task_id=request_data.task_id, concept_image_id=concept_image_db_id, status="failed")
                raise HTTPException(status_code=500, detail="No images were successfully uploaded to Supabase in synchronous mode.")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Synchronous OpenAI task failed for client task {request_data.task_id}: {e}", exc_info=True)
            # Attempt to update DB record to failed if possible
            if 'concept_image_db_id' in locals() and concept_image_db_id:
                try:
                    await supabase_handler.update_concept_image_record(task_id=request_data.task_id, concept_image_id=concept_image_db_id, status="failed")
                except Exception as db_update_e:
                    logger.error(f"Failed to update concept image record to failed: {db_update_e}")
            raise HTTPException(status_code=500, detail=f"Synchronous OpenAI task failed: {str(e)}")

    else: # Asynchronous (Celery) path
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

        logger.info(f"Sending OpenAI image generation task to Celery for db_id: {concept_image_db_id}")
        celery_task = generate_openai_image_task.delay(
            concept_image_db_id=concept_image_db_id, # Pass the DB record ID
            image_bytes=image_bytes,
            original_filename=request_data.input_image_asset_url.split('/')[-1], # Extract filename for reference
            request_data_dict=request_data.model_dump() # Pass other params like prompt, n, style, background
        )
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

@router.post("/text-to-model", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_TRIPO_OTHER_REQUESTS_PER_MINUTE}/minute")
async def generate_text_to_model_endpoint(request: Request, request_data: TextToModelRequest):
    """Initiates 3D model generation from text using Tripo AI."""
    logger.info(f"Received request for /generate/text-to-model for task_id: {request_data.task_id}")
    user_id_from_auth = TEST_USER_ID

    if settings.sync_mode:
        logger.info(f"Running Tripo text-to-model task synchronously for client task_id: {request_data.task_id}.")
        operation_id = str(uuid.uuid4())
        try:
            # Create initial record
            sync_db_record = await supabase_handler.create_model_record(
                task_id=request_data.task_id,
                prompt=request_data.prompt,
                style=request_data.style,
                status="processing",
                user_id=user_id_from_auth,  # Now None instead of invalid UUID
                ai_service_task_id=operation_id,
                metadata=request_data.model_dump(include={"texture", "pbr", "model_version", "face_limit", "auto_size", "texture_quality"})
            )
            model_db_id = sync_db_record["id"]

            # Call Tripo AI client directly (Simplified - actual client might need more setup or direct httpx call)
            # This part needs to align with how tripo_client.generate_text_to_model is structured
            # Assuming tripo_client.generate_text_to_model would return a structure with a temporary URL or data
            # For now, we'll simulate a successful AI call and asset upload for sync mode.
            # In a real scenario, this would involve: AI call -> get temp URL -> download -> upload to our Supabase
            
            logger.info(f"Sync task {operation_id}: Simulated Tripo AI call.")
            # Simulate downloading/creating asset data
            simulated_asset_data = b"simulated_glb_data"
            simulated_filename = "model.glb"
            
            # Upload to our Supabase
            final_asset_url = await supabase_handler.upload_asset_to_storage(
                task_id=request_data.task_id,
                asset_type_plural="models",
                file_name=simulated_filename,
                asset_data=simulated_asset_data,
                content_type="model/gltf-binary"
            )

            # Update model record
            await supabase_handler.update_model_record(
                task_id=request_data.task_id,
                model_id=model_db_id,
                asset_url=final_asset_url,
                status="complete",
                ai_service_task_id=operation_id,
                prompt=request_data.prompt,
                style=request_data.style
            )

            sync_task_results[operation_id] = {"status": "complete", "result_url": final_asset_url}
            logger.info(f"Sync task {operation_id}: Stored result. Returning this as task_id for polling.")
            return TaskIdResponse(celery_task_id=operation_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Synchronous Tripo text-to-model failed for client task {request_data.task_id}: {e}", exc_info=True)
            if 'model_db_id' in locals() and model_db_id:
                try:
                    await supabase_handler.update_model_record(task_id=request_data.task_id, model_id=model_db_id, status="failed")
                except Exception as db_e:
                    logger.error(f"Failed to update model record to failed: {db_e}")
            raise HTTPException(status_code=500, detail=f"Synchronous Tripo text-to-model failed: {str(e)}")

    else: # Asynchronous (Celery) path
        try:
            db_record = await supabase_handler.create_model_record(
                task_id=request_data.task_id,
                prompt=request_data.prompt,
                style=request_data.style,
                status="pending",
                user_id=user_id_from_auth,
                metadata=request_data.model_dump(include={"texture", "pbr", "model_version", "face_limit", "auto_size", "texture_quality"})
            )
            model_db_id = db_record["id"]
            logger.info(f"Created model record {model_db_id} for task {request_data.task_id}")

            logger.info(f"Sending Tripo AI text-to-model task to Celery for model_db_id: {model_db_id}")
            celery_task = generate_tripo_text_to_model_task.delay(
                model_db_id=model_db_id,
                request_data_dict=request_data.model_dump()
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
            logger.error(f"Error in /text-to-model endpoint for task {request_data.task_id}: {e}", exc_info=True)
            # Attempt to update status to failed if db_record was created
            if 'model_db_id' in locals() and model_db_id:
                try:
                    await supabase_handler.update_model_record(task_id=request_data.task_id, model_id=model_db_id, status="failed")
                except Exception as db_update_e:
                    logger.error(f"Failed to update model record to failed: {db_update_e}")
            raise HTTPException(status_code=500, detail=f"Failed to process text-to-model request: {str(e)}")

@router.post("/image-to-model", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_TRIPO_OTHER_REQUESTS_PER_MINUTE}/minute")
async def generate_image_to_model_endpoint(request: Request, request_data: ImageToModelRequest):
    """Initiates 3D model generation from multiple images (Supabase URLs) using Tripo AI."""
    logger.info(f"Received request for /generate/image-to-model for task_id: {request_data.task_id}")
    user_id_from_auth = TEST_USER_ID

    if settings.sync_mode:
        logger.info(f"Running Tripo image-to-model task synchronously for client task_id: {request_data.task_id}.")
        operation_id = str(uuid.uuid4())
        try:
            image_bytes_list = []
            original_filenames = []
            for url in request_data.input_image_asset_urls:
                try:
                    img_bytes = await supabase_handler.fetch_asset_from_storage(url)
                    image_bytes_list.append(img_bytes)
                    original_filenames.append(url.split('/')[-1])
                except Exception as fetch_e:
                    logger.error(f"Failed to fetch image {url} for task {request_data.task_id}: {fetch_e}")
                    raise HTTPException(status_code=400, detail=f"Failed to fetch one or more input images: {url}")
            
            if not image_bytes_list:
                raise HTTPException(status_code=400, detail="No input images could be fetched.")

            sync_db_record = await supabase_handler.create_model_record(
                task_id=request_data.task_id,
                prompt=request_data.prompt,
                style=request_data.style,
                status="processing",
                user_id=user_id_from_auth,
                ai_service_task_id=operation_id,
                source_concept_image_id=None,  # No concept image in direct image-to-model workflow
                metadata=request_data.model_dump(include={"texture", "pbr", "model_version", "face_limit", "auto_size", "texture_quality", "orientation"})
            )
            model_db_id = sync_db_record["id"]

            # Simplified: Simulate AI call and asset upload for sync mode
            logger.info(f"Sync task {operation_id}: Simulated Tripo AI image-to-model call.")
            simulated_asset_data = b"simulated_multiview_glb_data"
            simulated_filename = "model_multiview.glb"
            
            final_asset_url = await supabase_handler.upload_asset_to_storage(
                task_id=request_data.task_id,
                asset_type_plural="models",
                file_name=simulated_filename,
                asset_data=simulated_asset_data,
                content_type="model/gltf-binary"
            )

            await supabase_handler.update_model_record(
                task_id=request_data.task_id,
                model_id=model_db_id,
                asset_url=final_asset_url,
                status="complete",
                prompt=request_data.prompt,
                style=request_data.style,
                ai_service_task_id=operation_id
            )

            sync_task_results[operation_id] = {"status": "complete", "result_url": final_asset_url}
            return TaskIdResponse(celery_task_id=operation_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Synchronous Tripo image-to-model failed: {e}", exc_info=True)
            if 'model_db_id' in locals() and model_db_id:
                try:
                    await supabase_handler.update_model_record(task_id=request_data.task_id, model_id=model_db_id, status="failed")
                except: pass # best effort
            raise HTTPException(status_code=500, detail=f"Synchronous Tripo image-to-model failed: {str(e)}")

    else: # Asynchronous (Celery) path
        try:
            image_bytes_list = []
            original_filenames = []
            for url in request_data.input_image_asset_urls:
                try:
                    img_bytes = await supabase_handler.fetch_asset_from_storage(url)
                    image_bytes_list.append(img_bytes)
                    original_filenames.append(url.split('/')[-1])
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
                source_concept_image_id=None,  # No concept image in direct image-to-model workflow
                metadata=request_data.model_dump(include={"texture", "pbr", "model_version", "face_limit", "auto_size", "texture_quality", "orientation"})
                # Note: source_input_asset_id could be used to track input assets if we create input_assets records
            )
            model_db_id = db_record["id"]
            logger.info(f"Created model record {model_db_id} for image-to-model task {request_data.task_id}")

            celery_task = generate_tripo_image_to_model_task.delay(
                model_db_id=model_db_id,
                image_bytes_list=image_bytes_list,
                original_filenames=original_filenames,
                request_data_dict=request_data.model_dump()
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
            logger.error(f"Error in /image-to-model endpoint for task {request_data.task_id}: {e}", exc_info=True)
            if 'model_db_id' in locals() and model_db_id:
                try:
                    await supabase_handler.update_model_record(task_id=request_data.task_id, model_id=model_db_id, status="failed")
                except: pass # best effort
            raise HTTPException(status_code=500, detail=f"Failed to process image-to-model request: {str(e)}")

@router.post("/sketch-to-model", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_TRIPO_OTHER_REQUESTS_PER_MINUTE}/minute")
async def generate_sketch_to_model_endpoint(request: Request, request_data: SketchToModelRequest):
    """Initiates 3D model generation from a single sketch image (Supabase URL) using Tripo AI."""
    logger.info(f"Received request for /generate/sketch-to-model for task_id: {request_data.task_id}")
    user_id_from_auth = TEST_USER_ID

    if settings.sync_mode:
        logger.info(f"Running Tripo sketch-to-model task synchronously for client task_id: {request_data.task_id}.")
        operation_id = str(uuid.uuid4())
        try:
            image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_sketch_asset_url)
            if not image_bytes:
                raise HTTPException(status_code=404, detail="Failed to fetch input sketch from Supabase for sync mode.")

            sync_db_record = await supabase_handler.create_model_record(
                task_id=request_data.task_id,
                prompt=request_data.prompt,
                style=request_data.style,
                status="processing",
                user_id=user_id_from_auth,
                ai_service_task_id=operation_id,
                source_concept_image_id=None,  # No concept image in direct image-to-model workflow
                metadata=request_data.model_dump(include={"texture", "pbr", "model_version", "face_limit", "auto_size", "texture_quality", "orientation"})
                # Potentially add source_input_asset_id if the sketch corresponds to an input_assets entry
            )
            model_db_id = sync_db_record["id"]

            logger.info(f"Sync task {operation_id}: Simulated Tripo AI sketch-to-model call.")
            simulated_asset_data = b"simulated_sketch_glb_data"
            simulated_filename = "model_sketch.glb"
            
            final_asset_url = await supabase_handler.upload_asset_to_storage(
                task_id=request_data.task_id,
                asset_type_plural="models",
                file_name=simulated_filename,
                asset_data=simulated_asset_data,
                content_type="model/gltf-binary"
            )

            await supabase_handler.update_model_record(
                task_id=request_data.task_id,
                model_id=model_db_id,
                asset_url=final_asset_url,
                status="complete",
                prompt=request_data.prompt,
                style=request_data.style,
                ai_service_task_id=operation_id
            )

            sync_task_results[operation_id] = {"status": "complete", "result_url": final_asset_url}
            return TaskIdResponse(celery_task_id=operation_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Synchronous Tripo sketch-to-model failed: {e}", exc_info=True)
            if 'model_db_id' in locals() and model_db_id:
                try: await supabase_handler.update_model_record(task_id=request_data.task_id, model_id=model_db_id, status="failed")
                except: pass
            raise HTTPException(status_code=500, detail=f"Synchronous Tripo sketch-to-model failed: {str(e)}")

    else: # Asynchronous (Celery) path
        try:
            image_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_sketch_asset_url)
            
            db_record = await supabase_handler.create_model_record(
                task_id=request_data.task_id,
                prompt=request_data.prompt,
                style=request_data.style,
                status="pending",
                user_id=user_id_from_auth,
                source_concept_image_id=None,  # No concept image in direct image-to-model workflow
                metadata=request_data.model_dump(include={"texture", "pbr", "model_version", "face_limit", "auto_size", "texture_quality", "orientation"})
                # Potentially add source_input_asset_id
            )
            model_db_id = db_record["id"]
            logger.info(f"Created model record {model_db_id} for sketch-to-model task {request_data.task_id}")

            celery_task = generate_tripo_sketch_to_model_task.delay(
                model_db_id=model_db_id,
                image_bytes=image_bytes,
                original_filename=request_data.input_sketch_asset_url.split('/')[-1],
                request_data_dict=request_data.model_dump()
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
            logger.error(f"Error in /sketch-to-model endpoint for task {request_data.task_id}: {e}", exc_info=True)
            if 'model_db_id' in locals() and model_db_id:
                try: await supabase_handler.update_model_record(task_id=request_data.task_id, model_id=model_db_id, status="failed")
                except: pass
            raise HTTPException(status_code=500, detail=f"Failed to process sketch-to-model request: {str(e)}")

@router.post("/refine-model", response_model=TaskIdResponse)
@limiter.limit(f"{settings.BFF_TRIPO_REFINE_REQUESTS_PER_MINUTE}/minute")
async def refine_model_endpoint(request: Request, request_data: RefineModelRequest):
    """Refines an existing 3D model using Tripo AI."""
    logger.info(f"Received request for /refine-model for task_id: {request_data.task_id}")
    user_id_from_auth = TEST_USER_ID

    if settings.sync_mode:
        logger.info(f"Running Tripo refine-model task synchronously for client task_id: {request_data.task_id}.")
        operation_id = str(uuid.uuid4())
        try:
            model_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_model_asset_url)
            if not model_bytes:
                raise HTTPException(status_code=404, detail="Failed to fetch input model from Supabase for sync mode.")

            # Create a new model record for the refined output
            sync_db_record = await supabase_handler.create_model_record(
                task_id=request_data.task_id,
                prompt=request_data.prompt, # Refinement prompt
                # style could be None or from request_data if applicable for refine
                status="processing",
                user_id=user_id_from_auth,
                ai_service_task_id=operation_id,
                # input_model_asset_url is part of request_data.model_dump()
                metadata=request_data.model_dump(include={"texture", "pbr", "model_version", "face_limit", "auto_size", "texture_quality", "input_model_asset_url"})
            )
            refined_model_db_id = sync_db_record["id"]

            logger.info(f"Sync task {operation_id}: Simulated Tripo AI refine-model call.")
            simulated_refined_asset_data = b"simulated_refined_glb_data"
            simulated_refined_filename = "model_refined.glb"
            
            final_refined_asset_url = await supabase_handler.upload_asset_to_storage(
                task_id=request_data.task_id, # Use main task_id for folder structure
                asset_type_plural="models",
                file_name=simulated_refined_filename,
                asset_data=simulated_refined_asset_data,
                content_type="model/gltf-binary"
            )

            await supabase_handler.update_model_record(
                task_id=request_data.task_id,
                model_id=refined_model_db_id,
                asset_url=final_refined_asset_url,
                status="complete",
                prompt=request_data.prompt,
                ai_service_task_id=operation_id
            )

            sync_task_results[operation_id] = {"status": "complete", "result_url": final_refined_asset_url}
            return TaskIdResponse(celery_task_id=operation_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Synchronous Tripo refine-model failed: {e}", exc_info=True)
            if 'refined_model_db_id' in locals() and refined_model_db_id:
                try: await supabase_handler.update_model_record(task_id=request_data.task_id, model_id=refined_model_db_id, status="failed")
                except: pass
            raise HTTPException(status_code=500, detail=f"Synchronous Tripo refine-model failed: {str(e)}")

    else: # Asynchronous (Celery) path
        try:
            model_bytes = await supabase_handler.fetch_asset_from_storage(request_data.input_model_asset_url)

            # Create a new model record for the refined output
            db_record = await supabase_handler.create_model_record(
                task_id=request_data.task_id,
                prompt=request_data.prompt, # Refinement prompt
                # style=request_data.style, # If applicable for refine
                status="pending",
                user_id=user_id_from_auth,
                # Include input_model_asset_url in metadata to trace original model
                metadata=request_data.model_dump(include={"texture", "pbr", "model_version", "face_limit", "auto_size", "texture_quality", "input_model_asset_url"})
            )
            refined_model_db_id = db_record["id"]
            logger.info(f"Created new model record {refined_model_db_id} for refined output of task {request_data.task_id}")

            celery_task = generate_tripo_refine_model_task.delay(
                model_db_id=refined_model_db_id, # ID for the new record that will store the refined model
                model_bytes=model_bytes,
                original_filename=request_data.input_model_asset_url.split('/')[-1],
                request_data_dict=request_data.model_dump()
            )
            logger.info(f"Celery task ID: {celery_task.id} for refined_model_db_id: {refined_model_db_id}")

            await supabase_handler.update_model_record(
                task_id=request_data.task_id,
                model_id=refined_model_db_id,
                status="processing",
                ai_service_task_id=celery_task.id
            )
            return TaskIdResponse(celery_task_id=celery_task.id)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in /refine-model endpoint for task {request_data.task_id}: {e}", exc_info=True)
            if 'refined_model_db_id' in locals() and refined_model_db_id:
                try: await supabase_handler.update_model_record(task_id=request_data.task_id, model_id=refined_model_db_id, status="failed")
                except: pass
            raise HTTPException(status_code=500, detail=f"Failed to process refine-model request: {str(e)}")


# The /select-concept endpoint and its associated Celery task import have been removed.
# The SelectConceptRequest schema import is also removed from app.schemas.generation_schemas. 