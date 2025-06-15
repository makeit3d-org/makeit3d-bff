"""
API Key Authentication Module for MakeIT3D BFF
Provides multi-tenant authentication using X-API-Key header
"""

import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, Header, Depends
from datetime import datetime
import asyncio
from functools import lru_cache
import uuid
import hashlib
import secrets
import string

from supabase_client import get_supabase_client
from config import settings

logger = logging.getLogger(__name__)

class TenantContext:
    """Represents the authenticated tenant context"""
    def __init__(self, key_id: str, tenant_id: str, tenant_type: str, tenant_name: str, metadata: Dict[str, Any]):
        self.key_id = key_id
        self.tenant_id = tenant_id
        self.tenant_type = tenant_type
        self.tenant_name = tenant_name
        self.metadata = metadata
        
    def get_user_id(self) -> str:
        """Get a user ID for database operations - generates a deterministic UUID from tenant_id"""
        # Generate a deterministic UUID based on tenant_id
        # This ensures the same tenant always gets the same UUID
        namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # Standard namespace UUID
        return str(uuid.uuid5(namespace, self.tenant_id))
    
    def is_shopify_tenant(self) -> bool:
        """Check if this is a Shopify tenant"""
        return self.tenant_type == "shopify"
    
    def is_development(self) -> bool:
        """Check if this is a development tenant"""
        return self.tenant_type == "development"
    
    def __str__(self):
        return f"TenantContext(tenant_id={self.tenant_id}, type={self.tenant_type})"

class APIKeyValidator:
    """Handles API key validation and caching"""
    
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes cache
    
    @lru_cache(maxsize=1000)
    def _get_cached_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Cache API key lookups to reduce database calls"""
        # This will be populated by validate_api_key
        return None
    
    async def validate_api_key(self, api_key: str) -> Optional[TenantContext]:
        """
        Validate API key and return tenant context
        Returns None if key is invalid
        """
        if not api_key:
            return None
            
        # Check if key follows expected format
        if not api_key.startswith('makeit3d_'):
            logger.warning(f"Invalid API key format: {api_key[:20]}...")
            return None
        
        try:
            # Query database for API key
            def get_api_key():
                supabase = get_supabase_client()
                response = supabase.table('api_keys').select('*').eq('key_id', api_key).eq('is_active', True).execute()
                return response.data[0] if response.data else None
            
            # Run database query in thread pool to avoid blocking
            key_data = await asyncio.get_event_loop().run_in_executor(None, get_api_key)
            
            if not key_data:
                logger.warning(f"API key not found or inactive: {api_key[:20]}...")
                return None
            
            # Update last_used_at timestamp (fire and forget)
            asyncio.create_task(self._update_last_used(api_key))
            
            # Create tenant context
            tenant_context = TenantContext(
                key_id=key_data['key_id'],
                tenant_id=key_data['tenant_id'],
                tenant_type=key_data['tenant_type'],
                tenant_name=key_data.get('tenant_name', ''),
                metadata=key_data.get('metadata', {})
            )
            
            logger.info(f"Authenticated tenant: {tenant_context}")
            return tenant_context
            
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return None
    
    async def _update_last_used(self, api_key: str):
        """Update the last_used_at timestamp for the API key"""
        try:
            def update_timestamp():
                supabase = get_supabase_client()
                supabase.table('api_keys').update({
                    'last_used_at': datetime.utcnow().isoformat()
                }).eq('key_id', api_key).execute()
            
            await asyncio.get_event_loop().run_in_executor(None, update_timestamp)
        except Exception as e:
            logger.error(f"Failed to update last_used_at for API key: {e}")

# Global validator instance
api_key_validator = APIKeyValidator()

async def get_api_key_from_header(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Optional[str]:
    """Extract API key from X-API-Key header"""
    return x_api_key

async def get_current_tenant(api_key: Optional[str] = Depends(get_api_key_from_header)) -> TenantContext:
    """
    FastAPI dependency to get current authenticated tenant
    Raises HTTPException if authentication fails
    """
    # Allow development mode without API key
    if settings.ENVIRONMENT == "development" and not api_key:
        logger.info("Development mode: using test tenant context")
        return TenantContext(
            key_id="development",
            tenant_id="development_tenant",  # Use string tenant_id, UUID will be generated in get_user_id()
            tenant_type="development",
            tenant_name="Development Environment",
            metadata={"environment": "development"}
        )
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Please provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    tenant_context = await api_key_validator.validate_api_key(api_key)
    
    if not tenant_context:
        raise HTTPException(
            status_code=401,
            detail="Invalid or inactive API key.",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    return tenant_context

async def get_optional_tenant(api_key: Optional[str] = Depends(get_api_key_from_header)) -> Optional[TenantContext]:
    """
    Optional authentication - returns None if no valid API key provided
    Useful for endpoints that can work with or without authentication
    """
    if not api_key:
        return None
    
    return await api_key_validator.validate_api_key(api_key)

# Backward compatibility function
def get_user_id_from_tenant(tenant: TenantContext) -> str:
    """Get user ID for database operations from tenant context"""
    return tenant.get_user_id()

# API Key Generation Utilities

def generate_api_key(tenant_type: str, environment: str = "live") -> str:
    """
    Generate a new API key with the format: makeit3d_{env}_sk_{tenant_type}_{random}
    
    Args:
        tenant_type: Type of tenant (shopify, supabase_app, custom, development)
        environment: Environment (live, test)
    
    Returns:
        Generated API key string
    """
    # Generate random suffix (12 characters: letters and numbers)
    random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(12))
    
    # Create API key with format: makeit3d_{env}_sk_{tenant_type}_{random}
    api_key = f"makeit3d_{environment}_sk_{tenant_type}_{random_suffix}"
    
    return api_key

async def create_api_key_record(
    api_key: str,
    tenant_id: str,
    tenant_type: str,
    tenant_name: str = None,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Create a new API key record in the database
    
    Args:
        api_key: Generated API key
        tenant_id: Unique tenant identifier
        tenant_type: Type of tenant
        tenant_name: Human readable name
        metadata: Additional tenant information
    
    Returns:
        Created database record
    """
    try:
        def create_record():
            supabase = get_supabase_client()
            record_data = {
                'key_id': api_key,
                'tenant_id': tenant_id,
                'tenant_type': tenant_type,
                'tenant_name': tenant_name or tenant_id,
                'is_active': True,
                'metadata': metadata or {}
            }
            response = supabase.table('api_keys').insert(record_data).execute()
            return response.data[0] if response.data else None
        
        # Run database operation in thread pool
        record = await asyncio.get_event_loop().run_in_executor(None, create_record)
        
        if not record:
            raise Exception("Failed to create API key record")
        
        logger.info(f"Created API key record for tenant: {tenant_id} (type: {tenant_type})")
        return record
        
    except Exception as e:
        logger.error(f"Error creating API key record: {e}")
        raise 