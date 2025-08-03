import httpx
import logging
from typing import Dict, Any, Optional
from config import settings

logger = logging.getLogger(__name__)

class ReplicateClient:
    def __init__(self):
        self.api_key = settings.REPLICATE_API_KEY
        self.base_url = "https://api.replicate.com/v1"
        
    async def create_video_prediction(
        self,
        prompt: str,
        model: str = "kling-v2.1",
        mode: str = "standard", 
        duration: int = 5,
        start_image: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        aspect_ratio: str = "16:9",
        cfg_scale: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a video generation prediction using Replicate Kling v2.1 API.
        """
        endpoint = f"{self.base_url}/predictions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Map model to Replicate version
        model_versions = {
            "kling-v2.1": "kwaivgi/kling-v2.1"
        }
        
        version_id = model_versions.get(model, "kwaivgi/kling-v2.1")
        
        # Build input parameters
        input_data = {
            "prompt": prompt,
            "mode": mode,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "start_image": start_image  # Always include, even if None/null
        }
        
        # Add optional parameters
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt
        if cfg_scale is not None:
            input_data["cfg_scale"] = cfg_scale
            
        data = {
            "version": version_id,
            "input": input_data
        }
        
        logger.info(f"Creating Replicate prediction with data: {data}")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, json=data, headers=headers)
            
            if response.status_code != 201:
                logger.error(f"Replicate API error: {response.status_code} - {response.text}")
                response.raise_for_status()
                
            result = response.json()
            logger.info(f"Replicate prediction created: {result.get('id')}")
            return result
    
    async def get_prediction_status(self, prediction_id: str) -> Dict[str, Any]:
        """
        Get the status of a Replicate prediction.
        """
        endpoint = f"{self.base_url}/predictions/{prediction_id}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(endpoint, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Replicate status check error: {response.status_code} - {response.text}")
                response.raise_for_status()
                
            return response.json()
    
    async def cancel_prediction(self, prediction_id: str) -> Dict[str, Any]:
        """
        Cancel a Replicate prediction.
        """
        endpoint = f"{self.base_url}/predictions/{prediction_id}/cancel"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(endpoint, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Replicate cancel error: {response.status_code} - {response.text}")
                response.raise_for_status()
                
            return response.json()

# Create a global instance
replicate_client = ReplicateClient()