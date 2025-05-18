from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from typing_extensions import Annotated # Use typing_extensions for Annotated for broader compatibility

# Schemas for generation endpoints

class ImageToImageRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    n: Annotated[Optional[int], Field(ge=1, le=10)] = 1 # Number of images to generate, between 1 and 10, default to 1
    # Note: Image file is handled via multipart/form-data directly in the endpoint, not in this schema

class TextToModelRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    texture: bool = True

class ImageToModelRequest(BaseModel):
    image_urls: List[str]
    prompt: Optional[str] = None
    style: Optional[str] = None
    texture: bool = True

class SketchToModelRequest(BaseModel):
    image_url: str
    prompt: Optional[str] = None
    style: Optional[str] = None
    texture: bool = True

class RefineModelRequest(BaseModel):
    draft_model_task_id: str

class SelectConceptRequest(BaseModel):
    concept_task_id: str # Assuming we pass the original image-to-image task ID
    selected_image_url: str # Assuming we pass the URL of the selected concept image
    # Need to confirm if Tripo's image-to-model supports taking a URL from an external source like OpenAI's temporary URL

# Schemas for responses

class TaskIdResponse(BaseModel):
    task_id: str

class ImageToImageResponse(BaseModel):
    task_id: str
    # URLs of uploaded images in Supabase Storage
    image_urls: List[str] # Now returning Supabase Storage URLs

class TaskStatusResponse(BaseModel):
    status: str # e.g., pending, processing, completed, failed
    progress: Optional[float] = None # 0-100 for Tripo, None for OpenAI
    result_url: Optional[str] = None # Temporary URL for the generated asset
    result: Optional[Dict[str, Any]] = None # Add an optional result field to hold varied results
    # May need additional fields depending on normalized status details

class ErrorResponse(BaseModel):
    detail: str

# New schemas for OpenAI task results

class OpenAIResult(BaseModel):
    image_data: List[str]

class OpenAICompletedTaskStatusResponse(BaseModel):
    status: str = "completed"
    progress: float = 100.0
    result_url: Optional[str] = None # Not applicable for OpenAI concepts in this flow
    result: OpenAIResult 