import logging
import asyncio
import httpx
from typing import Dict, Any, Optional

from celery_worker import celery_app
from ai_clients.replicate_client import replicate_client
from schemas.generation_schemas import VideoGenerationRequest
from config import settings
import supabase_handler

logger = logging.getLogger(__name__)

# Custom exception for Celery tasks to ensure serializable errors
class CeleryTaskException(Exception):
    pass

@celery_app.task(bind=True, rate_limit="3/m")  # Conservative rate limit for video generation
def generate_video_task(self, video_db_id: str, request_data_dict: dict):
    """Celery task to call Replicate video generation, poll for completion, and update the DB record."""
    client_task_id = request_data_dict.get("task_id")
    celery_task_id = self.request.id
    
    logger.info(f"Starting video generation task {celery_task_id} for video_db_id: {video_db_id}")
    
    try:
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_generate_video_async(
            video_db_id, client_task_id, celery_task_id, request_data_dict
        ))
        loop.close()
        return result
        
    except Exception as e:
        logger.error(f"Video generation task {celery_task_id} failed: {e}", exc_info=True)
        
        # Update database record to failed status
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                supabase_handler.update_video_record(
                    task_id=client_task_id,
                    video_id=video_db_id,
                    status="failed",
                    error=str(e)
                )
            )
            loop.close()
        except Exception as db_error:
            logger.error(f"Failed to update video record to failed status: {db_error}")
        
        raise CeleryTaskException(f"Video generation failed: {str(e)}")

async def _generate_video_async(video_db_id: str, client_task_id: str, celery_task_id: str, request_data_dict: dict):
    """Async function to handle video generation workflow."""
    try:
        request_data = VideoGenerationRequest(**request_data_dict)

        logger.info(f"Creating {request_data.provider} video prediction for task {celery_task_id} using model {request_data.model}")
        
        # Route to appropriate provider client
        if request_data.provider == "replicate":
            prediction = await replicate_client.create_video_prediction(
                prompt=request_data.prompt,
                model=request_data.model,
                mode=request_data.mode,
                duration=request_data.duration,
                start_image=request_data.start_image,
                negative_prompt=request_data.negative_prompt,
                aspect_ratio=request_data.aspect_ratio,
                cfg_scale=request_data.cfg_scale
            )
            prediction_id = prediction["id"]
            provider_task_id = prediction_id
        else:
            raise Exception(f"Unsupported video generation provider: {request_data.provider}")
        
        logger.info(f"Created {request_data.provider} prediction {provider_task_id} for task {celery_task_id}")
        
        await supabase_handler.update_video_record(
            task_id=client_task_id,
            video_id=video_db_id,
            status="processing",
            ai_service_task_id=provider_task_id
        )
        
        max_polls = 120
        poll_count = 0
        
        while poll_count < max_polls:
            await asyncio.sleep(5)
            poll_count += 1
            
            try:
                # Poll status based on provider
                if request_data.provider == "replicate":
                    status_response = await replicate_client.get_prediction_status(provider_task_id)
                    status = status_response.get("status")
                    
                    logger.info(f"{request_data.provider} prediction {provider_task_id} status: {status} (poll {poll_count}/{max_polls})")
                    
                    if status == "succeeded" or status == "complete":
                        output_urls = status_response.get("output")
                        if not output_urls:
                            raise Exception(f"No output URLs returned from {request_data.provider}")
                        
                        video_url = output_urls[0] if isinstance(output_urls, list) else output_urls
                    elif status == "failed":
                        error_msg = status_response.get("error", "Unknown error")
                        logger.error(f"{request_data.provider} prediction {provider_task_id} failed: {error_msg}")
                        raise Exception(f"{request_data.provider} prediction failed: {error_msg}")
                    elif status == "canceled":
                        logger.warning(f"{request_data.provider} prediction {provider_task_id} was canceled")
                        raise Exception(f"{request_data.provider} prediction was canceled")
                    else:
                        continue  # Still processing
                else:
                    raise Exception(f"Status polling not implemented for provider: {request_data.provider}")
                
                # If we have a successful video generation, download and store it
                if 'video_url' in locals():
                    logger.info(f"Downloading video from: {video_url}")
                    
                    async with httpx.AsyncClient(timeout=300.0) as client:
                        response = await client.get(video_url)
                        response.raise_for_status()
                        video_bytes = response.content
                    
                    filename = f"{client_task_id}.mp4"
                    
                    asset_url = await supabase_handler.upload_asset_to_storage(
                        task_id=client_task_id,
                        asset_type_plural="videos",
                        file_name=filename,
                        asset_data=video_bytes,
                        content_type="video/mp4"
                    )
                    
                    await supabase_handler.update_video_record(
                        task_id=client_task_id,
                        video_id=video_db_id,
                        status="complete",
                        asset_url=asset_url,
                        metadata={
                            f"{request_data.provider}_task_id": provider_task_id,
                            **request_data.model_dump()
                        }
                    )
                    
                    logger.info(f"Video generation completed for task {celery_task_id}: {asset_url}")
                    return {
                        "task_id": celery_task_id, 
                        "asset_url": asset_url,
                        "provider": request_data.provider,
                        "service_type": "video"
                    }
                
            except Exception as poll_error:
                logger.error(f"Error polling prediction {provider_task_id}: {poll_error}")
                if poll_count >= max_polls:
                    raise poll_error
        
        logger.error(f"Video generation timed out after {max_polls} polls for prediction {provider_task_id}")
        
        # Try to cancel the timed-out prediction based on provider
        try:
            if request_data.provider == "replicate":
                await replicate_client.cancel_prediction(provider_task_id)
                logger.info(f"Canceled timed-out {request_data.provider} prediction {provider_task_id}")
        except Exception as cancel_error:
            logger.error(f"Failed to cancel {request_data.provider} prediction {provider_task_id}: {cancel_error}")
        
        raise Exception(f"Video generation timed out after {max_polls * 5} seconds")
        
    except Exception as e:
        logger.error(f"Video generation failed for task {celery_task_id}: {e}", exc_info=True)
        raise e