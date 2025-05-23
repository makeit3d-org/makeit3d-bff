from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Literal
from typing_extensions import Annotated # Use typing_extensions for Annotated for broader compatibility

# Schemas for generation endpoints

class ImageToImageRequest(BaseModel):
    """Request schema for image-to-image generation (OpenAI)."""
    task_id: str # Client-generated main task ID
    input_image_asset_url: str # Supabase URL to the input image
    prompt: str
    style: Optional[str] = None # Retain for potential frontend use or different models
    n: Optional[int] = Field(default=1, ge=1, le=10) # Number of images, default 1
    # Add other OpenAI parameters as needed, e.g., size, response_format
    # model: Optional[str] = "dall-e-2" # or "gpt-image-1" - client should set this
    background: Optional[str] = None # New field for background transparency

    @field_validator('background')
    def check_background_value(cls, value: Optional[str]):
        if value is not None and value not in ['transparent', 'opaque', 'auto']:
            raise ValueError("Background must be one of 'transparent', 'opaque', or 'auto'")
        return value

class TextToModelRequest(BaseModel):
    """Corresponds to Tripo AI text_to_model API."""
    task_id: str # Client-generated main task ID
    prompt: str
    style: Optional[str] = None
    texture: bool = True
    pbr: Optional[bool] = None  # Enable PBR texturing
    model_version: Optional[str] = None  # e.g., "v2.5-20250123"
    face_limit: Optional[int] = None  # Limit number of faces
    auto_size: Optional[bool] = None  # Auto scale to real-world dimensions
    texture_quality: Optional[Literal["standard", "detailed"]] = None

class FileInfo(BaseModel):
    """File information for Tripo API requests."""
    url: Optional[str] = None
    type: Optional[str] = "jpg"  # Default to jpg

class ImageToModelRequest(BaseModel):
    """Corresponds to Tripo AI multiview_to_model or image_to_model API."""
    task_id: str # Client-generated main task ID
    input_image_asset_urls: List[str]  # List of Supabase URLs to input images
    prompt: Optional[str] = None
    style: Optional[str] = None
    texture: bool = True
    pbr: Optional[bool] = None
    model_version: Optional[str] = None
    face_limit: Optional[int] = None
    auto_size: Optional[bool] = None
    texture_quality: Optional[Literal["standard", "detailed"]] = None
    orientation: Optional[Literal["default", "align_image"]] = None

class SketchToModelRequest(BaseModel):
    """Corresponds to Tripo AI image_to_model API."""
    task_id: str # Client-generated main task ID
    input_sketch_asset_url: str # Supabase URL to the input sketch
    prompt: Optional[str] = None
    style: Optional[str] = None
    texture: bool = True
    pbr: Optional[bool] = None
    model_version: Optional[str] = None
    face_limit: Optional[int] = None
    auto_size: Optional[bool] = None
    texture_quality: Optional[Literal["standard", "detailed"]] = None
    orientation: Optional[Literal["default", "align_image"]] = None

class RefineModelRequest(BaseModel):
    """Corresponds to Tripo AI refine_model API."""
    task_id: str # Client-generated main workspace task ID
    input_model_asset_url: str # Full Supabase URL to the 3D model that needs to be refined
    prompt: Optional[str] = None # Text prompt to guide the refinement process
    draft_model_task_id: Optional[str] = None # Optional Tripo task ID if input model is from previous Tripo task
    texture: bool = True # Whether to generate/regenerate textures for the model
    pbr: Optional[bool] = None # Enable PBR texturing
    model_version: Optional[str] = None # Tripo AI model version for refinement
    face_limit: Optional[int] = None # Limit number of faces on output refined model
    auto_size: Optional[bool] = None # Automatically scale refined model to real-world dimensions
    texture_quality: Optional[Literal["standard", "detailed"]] = None # Texture quality for refined model

# Schemas for responses

class TaskIdResponse(BaseModel):
    """Standard task ID response. The celery_task_id is used for polling the status of the current AI operation."""
    celery_task_id: str

class TripoApiResponse(BaseModel):
    """Standard Tripo API response structure."""
    code: int
    data: Dict[str, Any]
    
class TripoApiTaskResponse(TripoApiResponse):
    """Tripo API response for task creation."""
    data: Dict[str, str]  # Contains task_id

class TripoApiStatusResponse(TripoApiResponse):
    """Tripo API response for task status."""
    data: Dict[str, Any]  # Contains status, progress, etc.

class ImageToImageResponse(BaseModel):
    task_id: str
    # References to uploaded images in Supabase Storage
    image_references: List[Dict[str, str]] # Change to list of dictionaries for bucket and file_path

class TaskStatusResponse(BaseModel):
    """Response schema for the task status polling endpoint."""
    task_id: str # The Celery task ID of the job being polled
    status: str # pending, processing, complete, failed
    asset_url: Optional[str] = None # Full Supabase URL to the generated asset (only present if status is 'complete')
    error: Optional[str] = None # Error message if the task failed

class ErrorResponse(BaseModel):
    detail: str

# OpenAI schemas

class OpenAIResult(BaseModel):
    image_data: List[str] # This might need to change if we are returning Supabase URLs directly
    # If returning Supabase URLs, this might be: image_supabase_urls: List[str] 