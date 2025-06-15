"""
Authentication Router for MakeIT3D BFF
Handles API key registration and management
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any

# Import schemas following existing pattern
from schemas.generation_schemas import RegisterAPIKeyRequest, RegisterAPIKeyResponse, ErrorResponse

# Import auth utilities
from auth import generate_api_key, create_api_key_record

# Import configuration and dependencies following existing pattern
from config import settings
from limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/register", response_model=RegisterAPIKeyResponse)
@limiter.limit("10/minute")  # Rate limit registration attempts
async def register_api_key(request: Request, request_data: RegisterAPIKeyRequest):
    """
    Register a new API key for a tenant.
    
    This endpoint allows approved applications/stores to register and obtain
    an API key for accessing the MakeIT3D generation endpoints.
    """
    logger.info(f"Received API key registration request for tenant: {request_data.tenant_identifier} (type: {request_data.tenant_type})")
    
    # Verify the shared secret
    if request_data.verification_secret != settings.REGISTRATION_SECRET:
        logger.warning(f"Invalid verification secret for tenant: {request_data.tenant_identifier}")
        raise HTTPException(
            status_code=401,
            detail="Invalid verification secret. Access denied."
        )
    
    # Validate tenant_identifier format based on type
    if request_data.tenant_type == "shopify":
        if not request_data.tenant_identifier.endswith('.myshopify.com'):
            raise HTTPException(
                status_code=400,
                detail="Shopify tenant_identifier must be a valid .myshopify.com domain"
            )
    
    try:
        # Generate API key
        environment = "test" if settings.ENVIRONMENT == "development" else "live"
        api_key = generate_api_key(request_data.tenant_type, environment)
        
        # Prepare metadata
        metadata = request_data.metadata or {}
        metadata.update({
            "registered_at": "2025-06-14",  # Could use datetime.utcnow().isoformat()
            "environment": environment,
            "registration_source": "api"
        })
        
        # Create database record
        record = await create_api_key_record(
            api_key=api_key,
            tenant_id=request_data.tenant_identifier,
            tenant_type=request_data.tenant_type,
            tenant_name=request_data.tenant_name,
            metadata=metadata
        )
        
        logger.info(f"Successfully registered API key for tenant: {request_data.tenant_identifier}")
        
        return RegisterAPIKeyResponse(
            api_key=api_key,
            tenant_id=request_data.tenant_identifier,
            tenant_type=request_data.tenant_type,
            message=f"API key successfully registered for {request_data.tenant_type} tenant: {request_data.tenant_identifier}"
        )
        
    except Exception as e:
        logger.error(f"Error registering API key for tenant {request_data.tenant_identifier}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register API key: {str(e)}"
        )

@router.get("/health")
async def auth_health_check():
    """Health check endpoint for auth service."""
    return {"status": "healthy", "service": "auth"} 