import httpx
import logging
from typing import Dict, Any, Optional, List
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
    
    async def create_image_prediction(
        self,
        prompt: str,
        image_input: List[str],  # List of image URLs
        model: str = "nano-banana",
        output_format: str = "jpg"
    ) -> Dict[str, Any]:
        """
        Create an image generation prediction using Replicate API.
        
        Args:
            prompt: Text prompt for image generation
            image_input: List of input image URLs
            model: Model name (e.g., 'nano-banana')
            output_format: Output format ('jpg' or 'png')
            
        Returns:
            Dict containing prediction data
        """
        endpoint = f"{self.base_url}/predictions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Map model to full Replicate version string
        model_versions = {
            "nano-banana": "google/nano-banana"
        }
        
        version_id = model_versions.get(model, f"google/{model}")
        
        # Build input parameters for Google Nano Banana
        input_data = {
            "prompt": prompt,
            "output_format": output_format
        }
        
        # Add image_input if provided
        if image_input:
            input_data["image_input"] = image_input
        
        data = {
            "version": version_id,
            "input": input_data
        }
        
        logger.info(f"Creating Replicate image prediction with data: {data}")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, json=data, headers=headers)
            
            if response.status_code != 201:
                logger.error(f"Replicate API error: {response.status_code} - {response.text}")
                response.raise_for_status()
                
            result = response.json()
            logger.info(f"Replicate image prediction created: {result.get('id')}")
            return result

    async def download_prediction_output(self, output_url: str) -> bytes:
        """
        Download the generated image from Replicate output URL.
        
        Args:
            output_url: URL of the generated image
            
        Returns:
            Image data as bytes
        """
        logger.info(f"Downloading image from Replicate output URL: {output_url}")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(output_url)
            response.raise_for_status()
            
            logger.info(f"Successfully downloaded image: {len(response.content)} bytes")
            return response.content

# Create a global instance
replicate_client = ReplicateClient()