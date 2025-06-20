import pytest
import time
import uuid
import httpx
import os

# Import all shared helpers and utilities
from .test_helpers import (
    BASE_URL, logger, print_test_summary
)

# --- Authentication Tests ---

@pytest.mark.asyncio
async def test_auth_health_check(request):
    """Test auth health check endpoint."""
    start_time = time.time()
    
    print(f"\n🚀 Starting test: {request.node.name}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/auth/health"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        api_call_start = time.time()
        response = await client.get(endpoint)
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    assert result["status"] == "healthy"
    assert result["service"] == "auth"
    
    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    
    # Test summary
    timings = {"API Response Time": api_response_time}
    locations = {"api_endpoints": {"auth_health": endpoint}}
    print_test_summary(request.node.name, "auth-health-check", start_time, timings, locations)


@pytest.mark.asyncio
async def test_register_api_key_shopify(request):
    """Test API key registration for Shopify tenant."""
    start_time = time.time()
    tenant_id = f"test-shop-{uuid.uuid4().hex[:8]}.myshopify.com"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Tenant ID: {tenant_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/auth/register"
    
    # Get registration secret from environment (should match the one in .env)
    registration_secret = os.environ.get("REGISTRATION_SECRET", "n2K_KZX2PmFtF8Tn8_vDcqbP")
    
    request_data = {
        "verification_secret": registration_secret,
        "tenant_type": "shopify",
        "tenant_identifier": tenant_id,
        "tenant_name": "Test Shopify Store",
        "metadata": {
            "store_id": "12345",
            "plan": "basic",
            "test_registration": True
        }
    }

    logger.info(f"Calling {endpoint} with JSON data: {request_data}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    print(f"🌐 API Response received in {api_response_time:.2f}s")
    logger.info(f"Received response: {result}")

    # Verify response structure
    assert "api_key" in result
    assert "tenant_id" in result
    assert "tenant_type" in result
    assert "message" in result
    
    # Verify response values
    assert result["tenant_id"] == tenant_id
    assert result["tenant_type"] == "shopify"
    assert result["api_key"].startswith("makeit3d_live_sk_shopify_")
    assert "successfully registered" in result["message"]
    
    api_key = result["api_key"]
    print(f"🔑 Generated API Key: {api_key}")
    
    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    
    # Test summary
    timings = {"API Response Time": api_response_time}
    locations = {
        "api_endpoints": {"auth_register": endpoint},
        "generated_credentials": {"api_key": api_key, "tenant_id": tenant_id}
    }
    print_test_summary(request.node.name, tenant_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_register_api_key_supabase_app(request):
    """Test API key registration for Supabase app tenant."""
    start_time = time.time()
    tenant_id = f"test-app-{uuid.uuid4().hex[:8]}"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Tenant ID: {tenant_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/auth/register"
    
    # Get registration secret from environment
    registration_secret = os.environ.get("REGISTRATION_SECRET", "n2K_KZX2PmFtF8Tn8_vDcqbP")
    
    request_data = {
        "verification_secret": registration_secret,
        "tenant_type": "supabase_app",
        "tenant_identifier": tenant_id,
        "tenant_name": "Test Supabase App",
        "metadata": {
            "app_version": "1.0.0",
            "developer": "Test Developer",
            "test_registration": True
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        result = response.json()
        api_response_time = time.time() - api_call_start

    # Verify response
    assert result["tenant_id"] == tenant_id
    assert result["tenant_type"] == "supabase_app"
    assert result["api_key"].startswith("makeit3d_live_sk_supabase_app_")
    
    api_key = result["api_key"]
    print(f"🔑 Generated API Key: {api_key}")
    
    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    
    # Test summary
    timings = {"API Response Time": api_response_time}
    locations = {
        "api_endpoints": {"auth_register": endpoint},
        "generated_credentials": {"api_key": api_key, "tenant_id": tenant_id}
    }
    print_test_summary(request.node.name, tenant_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_register_api_key_invalid_secret(request):
    """Test API key registration with invalid secret."""
    start_time = time.time()
    tenant_id = f"test-invalid-{uuid.uuid4().hex[:8]}.myshopify.com"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Tenant ID: {tenant_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/auth/register"
    
    request_data = {
        "verification_secret": "invalid_secret_123",
        "tenant_type": "shopify",
        "tenant_identifier": tenant_id,
        "tenant_name": "Test Store"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers={"Content-Type": "application/json"})
        api_response_time = time.time() - api_call_start

    # Should return 401 for invalid secret
    assert response.status_code == 401
    result = response.json()
    assert "Invalid verification secret" in result["detail"]
    
    print(f"✅ Correctly rejected invalid secret with 401")
    
    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    
    # Test summary
    timings = {"API Response Time": api_response_time}
    locations = {"api_endpoints": {"auth_register": endpoint}}
    print_test_summary(request.node.name, tenant_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_register_api_key_invalid_shopify_domain(request):
    """Test API key registration with invalid Shopify domain."""
    start_time = time.time()
    tenant_id = "invalid-domain.com"  # Not a .myshopify.com domain
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Tenant ID: {tenant_id}")
    logger.info(f"TEST START: {start_time}")
    
    endpoint = f"{BASE_URL}/auth/register"
    
    # Get registration secret from environment
    registration_secret = os.environ.get("REGISTRATION_SECRET", "n2K_KZX2PmFtF8Tn8_vDcqbP")
    
    request_data = {
        "verification_secret": registration_secret,
        "tenant_type": "shopify",
        "tenant_identifier": tenant_id,
        "tenant_name": "Invalid Store"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        api_call_start = time.time()
        response = await client.post(endpoint, json=request_data, headers={"Content-Type": "application/json"})
        api_response_time = time.time() - api_call_start

    # Should return 400 for invalid domain
    assert response.status_code == 400
    result = response.json()
    assert "must be a valid .myshopify.com domain" in result["detail"]
    
    print(f"✅ Correctly rejected invalid Shopify domain with 400")
    
    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    
    # Test summary
    timings = {"API Response Time": api_response_time}
    locations = {"api_endpoints": {"auth_register": endpoint}}
    print_test_summary(request.node.name, tenant_id, start_time, timings, locations)


@pytest.mark.asyncio
async def test_api_key_usage_with_generation(request):
    """Test using a newly registered API key with a generation endpoint."""
    start_time = time.time()
    tenant_id = f"test-usage-{uuid.uuid4().hex[:8]}.myshopify.com"
    
    print(f"\n🚀 Starting test: {request.node.name}")
    print(f"📋 Tenant ID: {tenant_id}")
    logger.info(f"TEST START: {start_time}")
    
    # Step 1: Register a new API key
    register_endpoint = f"{BASE_URL}/auth/register"
    registration_secret = os.environ.get("REGISTRATION_SECRET", "n2K_KZX2PmFtF8Tn8_vDcqbP")
    
    register_data = {
        "verification_secret": registration_secret,
        "tenant_type": "shopify",
        "tenant_identifier": tenant_id,
        "tenant_name": "Test Usage Store"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        register_start = time.time()
        register_response = await client.post(register_endpoint, json=register_data, headers={"Content-Type": "application/json"})
        register_response.raise_for_status()
        register_result = register_response.json()
        register_time = time.time() - register_start

    api_key = register_result["api_key"]
    print(f"🔑 Registered API Key: {api_key}")
    
    # Step 2: Use the API key with a generation endpoint
    generation_endpoint = f"{BASE_URL}/generate/text-to-image"
    task_id = f"test-auth-usage-{uuid.uuid4().hex[:8]}"
    
    generation_data = {
        "task_id": task_id,
        "provider": "openai",
        "prompt": "A simple test image for authentication testing",
        "n": 1,
        "size": "1024x1024"
    }
    
    generation_headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        generation_start = time.time()
        generation_response = await client.post(generation_endpoint, json=generation_data, headers=generation_headers)
        generation_response.raise_for_status()
        generation_result = generation_response.json()
        generation_time = time.time() - generation_start

    # Verify the generation request was accepted
    assert "task_id" in generation_result
    task_id = generation_result["task_id"]
    print(f"🆔 Generation Task ID: {task_id}")
    
    total_test_time = time.time() - start_time
    print(f"⏱️ TOTAL TEST TIME: {total_test_time:.2f}s")
    
    # Test summary
    timings = {
        "API Key Registration": f"{register_time:.2f}s",
        "Generation Request": f"{generation_time:.2f}s"
    }
    locations = {
        "api_endpoints": {
            "auth_register": register_endpoint,
            "text_to_image": generation_endpoint
        },
        "generated_credentials": {"api_key": api_key, "tenant_id": tenant_id},
        "task_ids": {"generation_task": task_id}
    }
    print_test_summary(request.node.name, tenant_id, start_time, timings, locations) 
 
 
 