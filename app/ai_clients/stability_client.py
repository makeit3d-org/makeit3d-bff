import httpx
import logging
from typing import Dict, Any, Optional, List
from io import BytesIO
from config import settings

logger = logging.getLogger(__name__)

class StabilityClient:
    def __init__(self):
        self.api_key = settings.STABILITY_API_KEY
        self.base_url = "https://api.stability.ai"
        
    async def image_to_image(
        self,
        image_bytes: bytes,
        prompt: str,
        style_preset: Optional[str] = "3d-model",
        fidelity: float = 0.8,
        negative_prompt: Optional[str] = None,
        output_format: str = "png",
        seed: int = 0
    ) -> bytes:
        """
        Generate image from input image using Stability Structure Control.
        """
        endpoint = f"{self.base_url}/v2beta/stable-image/control/style"
        
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "accept": "image/*",
        }
        
        files = {
            "image": ("input_image.jpg", BytesIO(image_bytes), "image/jpeg")
        }
        
        data = {
            "prompt": prompt,
            "fidelity": fidelity,
            "output_format": output_format,
            "seed": seed
        }
        
        if negative_prompt:
            data["negative_prompt"] = negative_prompt
        if style_preset:
            data["style_preset"] = style_preset
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, files=files, data=data)
            response.raise_for_status()
            return response.content
    
    async def text_to_image(
        self,
        prompt: str,
        style_preset: Optional[str] = "3d-model",
        aspect_ratio: str = "1:1",
        negative_prompt: Optional[str] = None,
        output_format: str = "png",
        seed: int = 0
    ) -> bytes:
        """
        Generate image from text using Stability Image Core.
        """
        endpoint = f"{self.base_url}/v2beta/stable-image/generate/core"
        
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "accept": "image/*",
        }
        
        files = {"none": ""}  # Core model doesn't need image input for text-to-image
        
        data = {
            "prompt": prompt,
            "output_format": output_format,
            "aspect_ratio": aspect_ratio,
            "seed": seed
        }
        
        if negative_prompt:
            data["negative_prompt"] = negative_prompt
        if style_preset:
            data["style_preset"] = style_preset
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, files=files, data=data)
            response.raise_for_status()
            return response.content
    
    async def image_to_model(
        self,
        image_bytes: bytes,
        texture_resolution: int = 2048,
        remesh: Optional[str] = None,
        foreground_ratio: float = 1.3,
        target_type: str = "none",
        target_count: int = 10000,
        guidance_scale: int = 6,
        seed: int = 0
    ) -> bytes:
        """
        Generate 3D model from image using Stability SPAR3D.
        """
        endpoint = f"{self.base_url}/v2beta/3d/stable-point-aware-3d"
        
        headers = {
            "authorization": f"Bearer {self.api_key}",
        }
        
        files = {
            "image": ("input_image.png", BytesIO(image_bytes), "image/png")
        }
        
        data = {
            "texture_resolution": str(texture_resolution),
            "foreground_ratio": str(foreground_ratio),
            "target_type": target_type,
            "target_count": str(target_count),
            "guidance_scale": str(guidance_scale),
            "seed": str(seed)
        }
        
        if remesh is not None:
            data["remesh"] = remesh
            
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(endpoint, headers=headers, files=files, data=data)
            response.raise_for_status()
            return response.content
    
    async def sketch_to_image(
        self,
        sketch_bytes: bytes,
        prompt: str,
        control_strength: float = 0.4,
        style_preset: Optional[str] = "3d-model",
        negative_prompt: Optional[str] = None,
        output_format: str = "png"
    ) -> bytes:
        """
        Generate image from sketch using Stability Sketch Control.
        """
        endpoint = f"{self.base_url}/v2beta/stable-image/control/sketch"
        
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "accept": "image/*",
        }
        
        files = {
            "image": ("sketch.jpg", BytesIO(sketch_bytes), "image/jpeg")
        }
        
        data = {
            "prompt": prompt,
            "output_format": output_format,
            "control_strength": control_strength
        }
        
        if negative_prompt:
            data["negative_prompt"] = negative_prompt
        if style_preset:
            data["style_preset"] = style_preset
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, files=files, data=data)
            response.raise_for_status()
            return response.content
    
    async def remove_background(
        self,
        image_bytes: bytes,
        output_format: str = "png"
    ) -> bytes:
        """
        Remove background from image using Stability Remove Background.
        """
        endpoint = f"{self.base_url}/v2beta/stable-image/edit/remove-background"
        
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "accept": "image/*",
        }
        
        files = {
            "image": ("image.png", BytesIO(image_bytes), "image/png")
        }
        
        data = {
            "output_format": output_format
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, files=files, data=data)
            response.raise_for_status()
            return response.content

    async def search_and_recolor(
        self,
        image_bytes: bytes,
        prompt: str,
        select_prompt: str,
        negative_prompt: Optional[str] = None,
        grow_mask: int = 3,
        seed: int = 0,
        output_format: str = "png",
        style_preset: Optional[str] = None
    ) -> bytes:
        """
        Search for objects in an image and recolor them using Stability Search and Recolor.
        """
        endpoint = f"{self.base_url}/v2beta/stable-image/edit/search-and-recolor"
        
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "accept": "image/*",
        }
        
        files = {
            "image": ("image.png", BytesIO(image_bytes), "image/png")
        }
        
        data = {
            "prompt": prompt,
            "select_prompt": select_prompt,
            "output_format": output_format,
            "grow_mask": grow_mask,
            "seed": seed
        }
        
        if negative_prompt:
            data["negative_prompt"] = negative_prompt
        if style_preset:
            data["style_preset"] = style_preset
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, files=files, data=data)
            response.raise_for_status()
            return response.content

# Create a singleton instance
stability_client = StabilityClient() 