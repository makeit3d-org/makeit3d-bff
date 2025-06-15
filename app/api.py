from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import slowapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging

# Import routers - tasks, generation_image, generation_model, and auth
from routers import tasks, generation_image, generation_model, auth
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="MakeIt3D API",
    description="Image processing API for MakeIt3D and Maxflow",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routers
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(generation_image.router, prefix="/generate", tags=["generation-images"])
# Temporarily hide generation_model router from docs while keeping functionality
app.include_router(generation_model.router, prefix="/generate", tags=["generation-models"], include_in_schema=False)
app.include_router(auth.router, prefix="/auth", tags=["authentication"])

@app.get("/")
async def root():
    """Root endpoint - returns API information."""
    return {
        "message": "MakeIt3D API",
        "version": "1.0.0",
        "endpoints": {
            "tasks": "/tasks",
            "generation_images": "/generate (image endpoints)",
            "authentication": "/auth"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"} 