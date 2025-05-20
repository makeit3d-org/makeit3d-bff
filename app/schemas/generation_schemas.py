from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from typing_extensions import Annotated # Use typing_extensions for Annotated for broader compatibility

# Schemas for generation endpoints

class ImageToImageRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    n: Annotated[Optional[int], Field(ge=1, le=10)] = 1 # Number of images to generate, between 1 and 10, default to 1
    # Note: Image file is handled via multipart/form-data directly in the endpoint, not in this schema

class TextToModelRequest(BaseModel):
    """Corresponds to Tripo AI text_to_model API."""
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
    image_urls: List[str]  # Will be transformed to file/files in the client
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
    image_url: str  # Will be transformed to file in the client
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
    draft_model_task_id: str

class SelectConceptRequest(BaseModel):
    """For converting a 2D concept to 3D model."""
    concept_task_id: str  # Original image-to-image task ID
    selected_image_url: str  # URL of the selected concept image
    texture: bool = True
    pbr: Optional[bool] = None
    model_version: Optional[str] = None
    face_limit: Optional[int] = None
    auto_size: Optional[bool] = None
    texture_quality: Optional[Literal["standard", "detailed"]] = None

# Schemas for responses

class TaskIdResponse(BaseModel):
    """Standard task ID response."""
    task_id: str

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
    """Standardized task status response used across both OpenAI and Tripo."""
    status: str # e.g., pending, processing, completed, failed
    progress: Optional[float] = None # 0-100 for Tripo, None for OpenAI
    result_url: Optional[str] = None # Temporary URL for the generated asset
    result: Optional[Dict[str, Any]] = None # Add an optional result field to hold varied results
    # For completed OpenAI image tasks, 'result' will contain 'image_references': List[Dict[str, str]]
    # For completed Tripo tasks, result_url will point to the model file

class ErrorResponse(BaseModel):
    detail: str

# OpenAI schemas

class OpenAIResult(BaseModel):
    image_data: List[str]

class OpenAICompletedTaskStatusResponse(BaseModel):
    status: str = "completed"
    progress: float = 100.0
    result_url: Optional[str] = None # Not applicable for OpenAI concepts in this flow
    result: OpenAIResult 