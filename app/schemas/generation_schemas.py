from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any, Literal, Union
from typing_extensions import Annotated # Use typing_extensions for Annotated for broader compatibility

# Schemas for generation endpoints

class SearchAndRecolorRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    """Request schema for search and recolor generation (Stability only)."""
    task_id: str  # Client-generated main task ID
    provider: Literal["stability"] = "stability"  # Only Stability supports search-and-recolor
    input_image_asset_url: str  # Supabase URL to the input image
    prompt: str  # Description of how to recolor the object
    select_prompt: str  # What object to search for and recolor in the image
    
    # Stability parameters
    negative_prompt: Optional[str] = None  # What to avoid in the recoloring
    grow_mask: Optional[int] = Field(default=3, ge=0, le=20)  # Grows mask edges for smoother transitions
    seed: Optional[int] = 0  # Seed for reproducibility, 0 for random
    output_format: Optional[str] = "png"  # Output format: png, jpeg, webp
    style_preset: Optional[str] = None  # Optional style preset

class ImageToImageRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    """Request schema for image-to-image generation (multi-provider)."""
    task_id: str # Client-generated main task ID
    provider: Literal["openai", "stability", "recraft", "flux"] # AI provider to use
    input_image_asset_url: str # Supabase URL to the input image
    prompt: str
    
    # OpenAI parameters
    style: Optional[str] = None # OpenAI style
    n: Optional[int] = Field(default=1, ge=1, le=10) # Number of images, default 1
    background: Optional[str] = None # OpenAI background transparency
    
    # Stability parameters
    style_preset: Optional[str] = None # Stability style preset
    fidelity: Optional[float] = Field(default=0.8, ge=0.0, le=1.0) # Stability fidelity
    negative_prompt: Optional[str] = None # Stability negative prompt
    output_format: Optional[str] = "png" # Stability output format
    seed: Optional[int] = 0 # Stability seed
    
    # Recraft parameters
    substyle: Optional[str] = None # Recraft substyle
    strength: Optional[float] = Field(default=0.2, ge=0.0, le=1.0) # Recraft strength
    model: Optional[str] = "recraftv3" # Recraft model
    response_format: Optional[str] = "url" # Recraft response format
    style_id: Optional[str] = None # Recraft custom style ID
    
    # Flux parameters
    aspect_ratio: Optional[str] = "1:1" # Flux aspect ratio
    safety_tolerance: Optional[int] = Field(default=2, ge=0, le=6) # Flux safety tolerance
    prompt_upsampling: Optional[bool] = False # Flux prompt upsampling

    @field_validator('background')
    def check_background_value(cls, value: Optional[str]):
        if value is not None and value not in ['transparent', 'opaque', 'auto']:
            raise ValueError("Background must be one of 'transparent', 'opaque', or 'auto'")
        return value

class TextToImageRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    """Request schema for text-to-image generation (multi-provider)."""
    task_id: str # Client-generated main task ID
    provider: Literal["openai", "stability", "recraft", "flux"] # AI provider to use
    prompt: str
    
    # OpenAI parameters
    style: Optional[str] = None # OpenAI style
    n: Optional[int] = Field(default=1, ge=1, le=10) # Number of images
    size: Optional[str] = "1024x1024" # OpenAI size
    quality: Optional[str] = "standard" # OpenAI quality
    
    # Stability parameters
    style_preset: Optional[str] = None # Stability style preset
    aspect_ratio: Optional[str] = "1:1" # Stability aspect ratio
    negative_prompt: Optional[str] = None # Stability negative prompt
    output_format: Optional[str] = "png" # Stability output format
    seed: Optional[int] = 0 # Stability seed
    
    # Recraft parameters
    substyle: Optional[str] = None # Recraft substyle
    model: Optional[str] = "recraftv3" # Recraft model
    response_format: Optional[str] = "url" # Recraft response format
    style_id: Optional[str] = None # Recraft custom style ID
    
    # Flux parameters (for text-to-image)
    width: Optional[int] = 1024 # Flux image width
    height: Optional[int] = 1024 # Flux image height
    safety_tolerance: Optional[int] = Field(default=2, ge=0, le=6) # Flux safety tolerance
    prompt_upsampling: Optional[bool] = False # Flux prompt upsampling

class TextToModelRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    """Request schema for text-to-model generation (Tripo only)."""
    task_id: str # Client-generated main task ID
    provider: Literal["tripo"] # Only Tripo supports text-to-model
    prompt: str
    
    # Tripo parameters
    style: Optional[str] = None
    texture: bool = True
    pbr: Optional[bool] = None
    model_version: Optional[str] = None
    face_limit: Optional[int] = None
    auto_size: Optional[bool] = None
    texture_quality: Optional[Literal["standard", "detailed"]] = None

class FileInfo(BaseModel):
    """File information for Tripo API requests."""
    url: Optional[str] = None
    type: Optional[str] = "jpg"  # Default to jpg

class ImageToModelRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    """Request schema for image-to-model generation (multi-provider)."""
    task_id: str # Client-generated main task ID
    provider: Literal["tripo", "stability"] # AI provider to use
    input_image_asset_urls: List[str]  # List of Supabase URLs to input images
    
    # Tripo parameters
    prompt: Optional[str] = None
    style: Optional[str] = None
    texture: bool = True
    pbr: Optional[bool] = None
    model_version: Optional[str] = None
    face_limit: Optional[int] = None
    auto_size: Optional[bool] = None
    texture_quality: Optional[Literal["standard", "detailed"]] = None
    orientation: Optional[Literal["default", "align_image"]] = None
    
    # Stability parameters
    texture_resolution: Optional[int] = 2048
    remesh: Optional[str] = None
    foreground_ratio: Optional[float] = 1.3
    target_type: Optional[str] = "none"
    target_count: Optional[int] = 10000
    guidance_scale: Optional[int] = 6
    seed: Optional[int] = 0

class SketchToImageRequest(BaseModel):
    """Request schema for sketch-to-image generation (Stability only)."""
    task_id: str # Client-generated main task ID
    input_sketch_asset_url: str # Supabase URL to the input sketch
    prompt: str
    
    # Stability parameters
    control_strength: Optional[float] = Field(default=0.8, ge=0.0, le=1.0)
    style_preset: Optional[str] = "3d-model"
    negative_prompt: Optional[str] = None
    output_format: Optional[str] = "png"
    seed: Optional[int] = 0

class RefineModelRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    """Request schema for model refinement (Tripo only)."""
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

class RemoveBackgroundRequest(BaseModel):
    """Request schema for background removal (multi-provider)."""
    task_id: str # Client-generated main task ID
    provider: Literal["stability", "recraft"] # AI provider to use
    input_image_asset_url: str # Supabase URL to the input image
    
    # Stability parameters
    output_format: Optional[str] = "png" # Stability output format
    
    # Recraft parameters
    response_format: Optional[str] = "url" # Recraft response format

class UpscaleRequest(BaseModel):
    """Request schema for image upscaling (multi-provider)."""
    task_id: str # Client-generated main task ID
    provider: Literal["stability", "recraft"] # AI provider to use
    input_image_asset_url: str # Supabase URL to the input image
    
    # Shared parameters
    model: Optional[str] = None # Model to use: Stability: "fast", Recraft: "crisp" (default and only option)
    
    # Stability parameters
    output_format: Optional[str] = "png" # Stability output format
    
    # Recraft parameters
    response_format: Optional[str] = "url" # Recraft response format
    
    def __init__(self, **data):
        super().__init__(**data)
        # Set default model based on provider
        if self.model is None:
            if self.provider == "stability":
                self.model = "fast"
            elif self.provider == "recraft":
                self.model = "crisp"

class DownscaleRequest(BaseModel):
    """Request schema for image downscaling (basic image processing)."""
    task_id: str # Client-generated main task ID
    input_image_asset_url: str # Supabase URL to the input image
    max_size_mb: float = Field(ge=0.1, le=20.0) # Target maximum file size in megabytes
    aspect_ratio_mode: Literal["original", "square"] # Aspect ratio handling
    output_format: Literal["original", "jpeg", "png"] = "original" # Output format conversion
    
    @field_validator('max_size_mb')
    def validate_max_size_mb(cls, value: float):
        if value <= 0:
            raise ValueError("max_size_mb must be greater than 0")
        return value

class ImageInpaintRequest(BaseModel):
    """Request schema for image inpainting (Recraft only)."""
    task_id: str # Client-generated main task ID
    provider: str # Must be "recraft" for this endpoint
    input_image_asset_url: str # Supabase URL to the input image
    input_mask_asset_url: str # Supabase URL to the mask image
    prompt: str
    
    # Recraft parameters
    negative_prompt: Optional[str] = None
    n: Optional[int] = Field(default=1, ge=1, le=6)
    style: Optional[str] = "realistic_image"
    substyle: Optional[str] = None
    model: Optional[str] = "recraftv3"
    response_format: Optional[str] = "url"
    style_id: Optional[str] = None

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
    progress: Optional[int] = None # Progress percentage (0-100) for Tripo AI tasks

class ErrorResponse(BaseModel):
    detail: str

# Authentication Schemas

class RegisterAPIKeyRequest(BaseModel):
    """Request schema for API key registration."""
    verification_secret: str  # Shared secret for verification
    tenant_type: Literal["shopify", "supabase_app", "custom", "development"]  # Type of tenant
    tenant_identifier: str  # Unique identifier (store domain, app ID, etc.)
    tenant_name: Optional[str] = None  # Human readable name
    metadata: Optional[Dict[str, Any]] = None  # Additional tenant information

class RegisterAPIKeyResponse(BaseModel):
    """Response schema for API key registration."""
    api_key: str  # Generated API key
    tenant_id: str  # Tenant identifier
    tenant_type: str  # Type of tenant
    message: str  # Success message

# OpenAI schemas

class OpenAIResult(BaseModel):
    image_data: List[str] # This might need to change if we are returning Supabase URLs directly
    # If returning Supabase URLs, this might be: image_supabase_urls: List[str] 