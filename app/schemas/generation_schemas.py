from pydantic import BaseModel, Field, field_validator, ConfigDict, validator
from typing import List, Optional, Dict, Any, Literal, Union
from typing_extensions import Annotated # Use typing_extensions for Annotated for broader compatibility
from enum import Enum

# Schemas for generation endpoints

class SearchAndRecolorRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    """Request schema for search and recolor generation (Stability only)."""
    provider: str = Field(..., description="AI provider ('stability')")
    input_image_asset_url: str = Field(..., description="URL of the input image")
    prompt: str = Field(..., description="Search and recolor prompt")
    style_preset: Optional[str] = Field("photographic", description="Style preset")
    select_prompt: Optional[str] = Field(None, description="Search prompt for object selection")
    negative_prompt: Optional[str] = Field(None, description="Negative prompt")
    output_format: Optional[str] = Field("png", description="Output image format")
    
    # Stability parameters
    grow_mask: Optional[int] = Field(default=3, ge=0, le=20)  # Grows mask edges for smoother transitions
    seed: Optional[int] = 0  # Seed for reproducibility, 0 for random

class ImageToImageRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    """Request schema for image-to-image generation (multi-provider)."""
    provider: str = Field(..., description="AI provider (e.g., 'openai', 'stability', 'recraft', 'flux')")
    input_image_asset_url: str = Field(..., description="URL of the input image")
    prompt: str = Field(..., description="Text prompt for generation")
    style: Optional[str] = Field(None, description="Style preset for the generated image")
    model: Optional[str] = Field(None, description="Model variant")
    num_outputs: Optional[int] = Field(1, description="Number of outputs to generate")
    quality: Optional[str] = Field(None, description="Quality level")
    
    # OpenAI parameters
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
    provider: str = Field(..., description="AI provider (e.g., 'openai', 'stability', 'recraft', 'flux')")
    prompt: str = Field(..., description="Text prompt for generation")
    style: Optional[str] = Field(None, description="Style preset for the generated image")
    model: Optional[str] = Field(None, description="Model variant")
    width: Optional[int] = Field(None, description="Width of the generated image")
    height: Optional[int] = Field(None, description="Height of the generated image")
    num_outputs: Optional[int] = Field(1, description="Number of outputs to generate")
    quality: Optional[str] = Field(None, description="Quality level")
    
    # OpenAI parameters
    n: Optional[int] = Field(default=1, ge=1, le=10) # Number of images
    size: Optional[str] = "1024x1024" # OpenAI size
    
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
    safety_tolerance: Optional[int] = Field(default=2, ge=0, le=6) # Flux safety tolerance
    prompt_upsampling: Optional[bool] = False # Flux prompt upsampling

class TextToModelRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    """Request schema for text-to-model generation (Tripo only)."""
    provider: str = Field(..., description="AI provider ('tripoai')")
    prompt: str = Field(..., description="Text prompt for model generation")
    model_type: Optional[str] = Field(None, description="Type of model to generate")
    quality: Optional[str] = Field(None, description="Quality level")
    
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
    provider: str = Field(..., description="AI provider ('tripoai')")
    input_image_asset_url: str = Field(..., description="URL of the input image")
    prompt: Optional[str] = Field(None, description="Optional text prompt")
    model_type: Optional[str] = Field(None, description="Type of model to generate")
    quality: Optional[str] = Field(None, description="Quality level")
    
    # Tripo parameters
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
    input_sketch_asset_url: str = Field(..., description="URL of the input sketch")
    prompt: str = Field(..., description="Text prompt for generation")
    style_preset: Optional[str] = Field("photographic", description="Style preset (e.g., 'photographic', 'digital-art')")
    control_strength: Optional[float] = Field(0.7, description="Strength of control from sketch")
    output_format: Optional[str] = Field("png", description="Output image format")
    seed: Optional[int] = 0

class RefineModelRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    """Request schema for model refinement (Tripo only)."""
    provider: str = Field(..., description="AI provider ('tripoai')")
    input_model_asset_url: str = Field(..., description="URL of the input 3D model")
    prompt: Optional[str] = Field(None, description="Optional refinement prompt")
    quality: Optional[str] = Field(None, description="Quality level")
    draft_model_task_id: Optional[str] = None # Optional Tripo task ID if input model is from previous Tripo task
    texture: bool = True # Whether to generate/regenerate textures for the model
    pbr: Optional[bool] = None # Enable PBR texturing
    model_version: Optional[str] = None # Tripo AI model version for refinement
    face_limit: Optional[int] = None # Limit number of faces on output refined model
    auto_size: Optional[bool] = None # Automatically scale refined model to real-world dimensions
    texture_quality: Optional[Literal["standard", "detailed"]] = None # Texture quality for refined model

class RemoveBackgroundRequest(BaseModel):
    """Request schema for background removal (multi-provider)."""
    provider: str = Field(..., description="AI provider (e.g., 'stability', 'recraft')")
    input_image_asset_url: str = Field(..., description="URL of the input image")
    output_format: Optional[str] = Field("png", description="Output image format")
    
    @validator('provider')
    def validate_provider(cls, v):
        allowed_providers = ['stability', 'recraft']
        if v not in allowed_providers:
            raise ValueError(f'Provider must be one of: {allowed_providers}')
        return v

class UpscaleRequest(BaseModel):
    """Request schema for image upscaling (multi-provider)."""
    provider: str = Field(..., description="AI provider (e.g., 'stability', 'recraft')")
    input_image_asset_url: str = Field(..., description="URL of the input image")
    model: Optional[str] = Field(None, description="Upscaling model variant")
    prompt: Optional[str] = Field(None, description="Optional enhancement prompt")
    creativity: Optional[float] = Field(None, description="Creativity level (0.0-1.0)")
    resemblance: Optional[float] = Field(None, description="Resemblance to original (0.0-1.0)")
    output_format: Optional[str] = Field("png", description="Output image format")

    @validator('provider')
    def validate_provider(cls, v):
        allowed_providers = ['stability', 'recraft']
        if v not in allowed_providers:
            raise ValueError(f'Provider must be one of: {allowed_providers}')
        return v

class DownscaleRequest(BaseModel):
    """Request schema for image downscaling (basic image processing)."""
    input_image_asset_url: str = Field(..., description="URL of the input image")
    max_size_mb: float = Field(..., description="Target maximum file size in megabytes")
    aspect_ratio_mode: Optional[str] = Field("original", description="Aspect ratio handling")
    output_format: Optional[str] = Field("jpeg", description="Output format")
    quality: Optional[int] = Field(85, description="JPEG quality (1-100)")
    
    @field_validator('max_size_mb')
    def validate_max_size_mb(cls, value: float):
        if value <= 0:
            raise ValueError("max_size_mb must be greater than 0")
        return value

class ImageInpaintRequest(BaseModel):
    """Request schema for image inpainting (Recraft only)."""
    provider: str = Field(..., description="AI provider ('recraft')")
    input_image_asset_url: str = Field(..., description="URL of the input image")
    input_mask_asset_url: str = Field(..., description="URL of the mask image")
    prompt: str = Field(..., description="Inpainting prompt")
    style: Optional[str] = Field(None, description="Style preset")
    num_outputs: Optional[int] = Field(1, description="Number of outputs")
    
    # Recraft parameters
    negative_prompt: Optional[str] = None
    n: Optional[int] = Field(default=1, ge=1, le=6)
    substyle: Optional[str] = None
    model: Optional[str] = "recraftv3"
    response_format: Optional[str] = "url"
    style_id: Optional[str] = None

class VideoGenerationRequest(BaseModel):
    """Request schema for video generation. Supports multiple providers and models."""
    provider: str = Field(..., description="AI provider (e.g., 'replicate')")
    prompt: str = Field(..., description="Text prompt for video generation")
    start_image: Optional[str] = Field(None, description="Optional URL of the input image to use as the starting frame.")
    model: str = Field(..., description="Model variant (e.g., 'kling-v2.1')")
    mode: Optional[str] = Field("standard", description="Resolution mode: 'standard' (720p) or 'pro' (1080p)")
    duration: Optional[int] = Field(5, description="Video duration in seconds: 5 or 10")
    negative_prompt: Optional[str] = Field(None, description="Negative prompt to exclude elements")
    aspect_ratio: Optional[str] = Field("16:9", description="Aspect ratio: '16:9', '9:16', or '1:1'")
    cfg_scale: Optional[float] = Field(0.5, description="CFG (Classifier Free Guidance) scale. Range: 0.0-1.0. Higher values stick closer to prompt.")
    
    @field_validator('provider')
    def validate_provider(cls, v):
        # Allow multiple providers for video generation
        allowed_providers = ['replicate']  # Can be extended for future providers
        if v not in allowed_providers:
            raise ValueError(f"Provider must be one of: {allowed_providers}")
        return v
    
    @field_validator('mode')
    def validate_mode(cls, v):
        if v not in ['standard', 'pro']:
            raise ValueError("Mode must be 'standard' or 'pro'")
        return v
    
    @field_validator('duration')
    def validate_duration(cls, v):
        if v not in [5, 10]:
            raise ValueError("Duration must be 5 or 10 seconds")
        return v
    
    @field_validator('aspect_ratio')
    def validate_aspect_ratio(cls, v):
        if v not in ['16:9', '9:16', '1:1']:
            raise ValueError("Aspect ratio must be '16:9', '9:16', or '1:1'")
        return v
    
    @field_validator('cfg_scale')
    def validate_cfg_scale(cls, v):
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("cfg_scale must be between 0.0 and 1.0")
        return v


# Schemas for responses

class TaskIdResponse(BaseModel):
    """Standard task ID response. The task_id is used for polling the status of the current AI operation."""
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