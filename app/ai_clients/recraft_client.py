import httpx
import logging
from typing import Dict, Any, Optional, List
from io import BytesIO
from app.config import settings

logger = logging.getLogger(__name__)

class RecraftClient:
    def __init__(self):
        self.api_key = settings.recraft_api_key
        self.base_url = "https://external.api.recraft.ai"
        
    async def create_custom_style(
        self,
        style_reference_bytes: bytes,
        base_style: str = "digital_illustration"
    ) -> str:
        """
        Create a custom style using a reference image.
        Returns the style ID.
        """
        endpoint = f"{self.base_url}/v1/styles"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        files = {
            "file1": ("reference.png", BytesIO(style_reference_bytes), "image/png")
        }
        
        data = {
            "style": base_style
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, files=files, data=data)
            response.raise_for_status()
            response_data = response.json()
            
            style_id = response_data.get("id")
            if not style_id:
                raise ValueError("No style ID returned in response")
            
            return style_id
    
    async def image_to_image(
        self,
        image_bytes: bytes,
        prompt: str,
        style: str = "realistic_image",
        substyle: Optional[str] = None,
        strength: float = 0.2,
        negative_prompt: Optional[str] = None,
        n: int = 1,
        model: str = "recraftv3",
        response_format: str = "url",
        style_id: Optional[str] = None
    ) -> List[str]:
        """
        Generate image from input image using Recraft Image-to-Image.
        Returns list of image URLs.
        """
        endpoint = f"{self.base_url}/v1/images/imageToImage"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        files = {
            "image": ("input_image.jpg", BytesIO(image_bytes), "image/jpeg")
        }
        
        data = {
            "prompt": prompt,
            "strength": strength,
            "n": n,
            "model": model,
            "response_format": response_format
        }
        
        # Use custom style_id if provided, otherwise use base style
        if style_id:
            data["style_id"] = style_id
        else:
            data["style"] = style
            
        if negative_prompt:
            data["negative_prompt"] = negative_prompt
        if substyle:
            data["substyle"] = substyle
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, files=files, data=data)
            response.raise_for_status()
            response_data = response.json()
            
            # Extract image URLs from response
            image_urls = []
            if response_data.get("data"):
                for img_obj in response_data["data"]:
                    if img_obj.get("url"):
                        image_urls.append(img_obj["url"])
            
            return image_urls
    
    async def text_to_image(
        self,
        prompt: str,
        style: str = "realistic_image",
        substyle: Optional[str] = None,
        n: int = 1,
        model: str = "recraftv3",
        response_format: str = "url",
        size: str = "1024x1024",
        style_id: Optional[str] = None
    ) -> List[str]:
        """
        Generate image from text using Recraft Text-to-Image.
        Returns list of image URLs.
        """
        endpoint = f"{self.base_url}/v1/images/textToImage"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "prompt": prompt,
            "n": n,
            "model": model,
            "response_format": response_format,
            "size": size
        }
        
        # Use custom style_id if provided, otherwise use base style
        if style_id:
            data["style_id"] = style_id
        else:
            data["style"] = style
            
        if substyle:
            data["substyle"] = substyle
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, json=data)
            response.raise_for_status()
            response_data = response.json()
            
            # Extract image URLs from response
            image_urls = []
            if response_data.get("data"):
                for img_obj in response_data["data"]:
                    if img_obj.get("url"):
                        image_urls.append(img_obj["url"])
            
            return image_urls
    
    async def remove_background(
        self,
        image_bytes: bytes,
        response_format: str = "url"
    ) -> str:
        """
        Remove background from image using Recraft Remove Background.
        Returns image URL.
        """
        endpoint = f"{self.base_url}/v1/images/removeBackground"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        files = {
            "file": ("image.png", BytesIO(image_bytes), "image/png")
        }
        
        data = {
            "response_format": response_format
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, files=files, data=data)
            response.raise_for_status()
            response_data = response.json()
            
            # Extract image URL from response
            if response_data.get("image") and response_data["image"].get("url"):
                return response_data["image"]["url"]
            else:
                raise ValueError("No background-removed image URL found in response")
    
    async def inpaint(
        self,
        image_bytes: bytes,
        mask_bytes: bytes,
        prompt: str,
        negative_prompt: Optional[str] = None,
        n: int = 1,
        style: str = "realistic_image",
        substyle: Optional[str] = None,
        model: str = "recraftv3",
        response_format: str = "url",
        style_id: Optional[str] = None
    ) -> List[str]:
        """
        Inpaint image using mask with Recraft Inpaint.
        Returns list of image URLs.
        """
        endpoint = f"{self.base_url}/v1/images/inpaint"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        files = {
            "image": ("input_image.png", BytesIO(image_bytes), "image/png"),
            "mask": ("mask_image.png", BytesIO(mask_bytes), "image/png")
        }
        
        data = {
            "prompt": prompt,
            "n": n,
            "model": model,
            "response_format": response_format
        }
        
        # Use custom style_id if provided, otherwise use base style
        if style_id:
            data["style_id"] = style_id
        else:
            data["style"] = style
            
        if negative_prompt:
            data["negative_prompt"] = negative_prompt
        if substyle:
            data["substyle"] = substyle
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, files=files, data=data)
            response.raise_for_status()
            response_data = response.json()
            
            # Extract image URLs from response
            image_urls = []
            if response_data.get("data"):
                for img_obj in response_data["data"]:
                    if img_obj.get("url"):
                        image_urls.append(img_obj["url"])
            
            return image_urls
    
    async def download_image(self, image_url: str) -> bytes:
        """
        Download image from URL and return bytes.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            return response.content

# Create a singleton instance
recraft_client = RecraftClient() 