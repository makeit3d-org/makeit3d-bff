from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    TRIPO_API_KEY: str
    OPENAI_API_KEY: str
    STABILITY_API_KEY: str
    RECRAFT_API_KEY: str
    REPLICATE_API_KEY: str
    FLUX_API_KEY: str
    REDIS_URL: str = "redis://localhost:6379/0" # Default Redis URL for local development
    BFF_BASE_URL: str # Add setting for BFF base URL
    test_assets_mode: bool = False # Controls Supabase storage paths: test_outputs/ vs production paths
    
    # Environment Configuration
    ENVIRONMENT: str = "production"  # "development" or "production" - affects API key requirements
    
    # Authentication Configuration
    REGISTRATION_SECRET: str  # Shared secret for API key registration

    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    input_assets_table_name: str = "input_assets"
    images_table_name: str = "images"
    models_table_name: str = "models"
    generated_assets_bucket_name: str = "makeit3d-app-assets"

    # Tripo AI Configuration
    TRIPO_DOWNLOAD_TIMEOUT_SECONDS: int = 60  # Timeout for downloading models from Tripo URLs

    # Add other settings here as needed

    # API Rate Limiting for BFF endpoints
    BFF_OPENAI_REQUESTS_PER_MINUTE: int = 4
    BFF_TRIPO_REFINE_REQUESTS_PER_MINUTE: int = 2 # e.g. 6 requests to BFF for refine per minute (5 workers)
    BFF_TRIPO_OTHER_REQUESTS_PER_MINUTE: int = 4  # e.g. 12 requests to BFF for other Tripo tasks per minute (10 workers)
    # Note: These are per-minute request limits for the BFF API itself.
    # OpenAI actual image limit is 5 images/min. If n > 1 is used, this might need adjustment or smarter counting.
    # Tripo actual limits are concurrency-based (Refine: 5, Other: 10).
    # These BFF RPM values should be set to prevent Celery queues from growing excessively long,
    # considering the processing capacity of the dedicated Celery workers.

    # Celery Task Rate Limiting for OpenAI (global limit for tasks processed by Celery workers)
    CELERY_OPENAI_TASK_RATE_LIMIT: str = "5/m" # Aims for 5 OpenAI image generation tasks per minute globally

    # Removed Celery Task Rate Limiting strings for Tripo, as concurrency is now handled by worker counts.

    model_config = SettingsConfigDict(env_file=None, case_sensitive=False, extra='ignore')

settings = Settings() 