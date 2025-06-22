import requests
import time
import uuid

def register_api_key(verification_secret, tenant_type, tenant_identifier, tenant_name, metadata=None):
    """
    Register for a production API key with the MakeIt3D API.
    
    Args:
        verification_secret (str): Secret key for verification (obtain from MakeIt3D)
        tenant_type (str): Type of application ('supabase_app' or 'shopify')
        tenant_identifier (str): Unique identifier for your application
        tenant_name (str): Human-readable display name for your app
        metadata (dict, optional): Additional information about your application
    
    Returns:
        dict: Registration response containing api_key, tenant_id, etc.
    """
    if metadata is None:
        metadata = {}
    
    registration_data = {
        'verification_secret': verification_secret,
        'tenant_type': tenant_type,
        'tenant_identifier': tenant_identifier,
        'tenant_name': tenant_name,
        'metadata': metadata
    }
    
    response = requests.post(
        'https://api.makeit3d.io/auth/register',  # Real production API
        headers={'Content-Type': 'application/json'},
        json=registration_data
    )
    
    if response.status_code != 200:
        raise Exception(f"Registration failed: {response.status_code} - {response.text}")
    
    return response.json()

def remove_background(image_url, api_key, provider="stability"):
    """
    Remove background from an image using the MakeIt3D API.
    
    Args:
        image_url (str): URL to the source image
        api_key (str): Your MakeIt3D API key
        provider (str): AI provider to use ("stability" or "recraft")
    
    Returns:
        str: URL to the processed image with background removed
    """
    # 1. Submit job - BFF will generate the task ID
    response = requests.post(
        'https://api.makeit3d.io/generate/remove-background',  # Real production API
        headers={
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        },
        json={
            'provider': provider,
            'input_image_asset_url': image_url
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"Job submission failed: {response.status_code} - {response.text}")
    
    # 2. BFF returns the task ID it generated
    result = response.json()
    task_id = result['task_id']  # BFF-generated task ID
    
    print(f"Job submitted with BFF-generated task ID: {task_id}")
    
    # 3. Poll using the BFF-provided task ID
    while True:
        status_response = requests.get(
            f'https://api.makeit3d.io/tasks/{task_id}/status',  # Real production API
            headers={'X-API-Key': api_key}
        )
        
        if status_response.status_code != 200:
            # Get the response text for debugging
            try:
                error_details = status_response.json()
            except:
                error_details = status_response.text
            raise Exception(f"Status check failed: {status_response.status_code} - {error_details}")
        
        status = status_response.json()
        print(f"Status: {status['status']}")
        
        if status['status'] == 'complete':
            print(f"✅ Processing complete!")
            return status['asset_url']
        elif status['status'] == 'failed':
            raise Exception(f"Task failed: {status.get('error', 'Unknown error')}")
        
        time.sleep(2)  # Wait 2 seconds before next poll

def upscale_image(image_url, api_key, provider="stability"):
    """
    Upscale an image using the MakeIt3D API.
    
    Args:
        image_url (str): URL to the source image
        api_key (str): Your MakeIt3D API key
        provider (str): AI provider to use ("stability" or "recraft")
    
    Returns:
        str: URL to the upscaled image
    """
    # 1. Submit upscale job - BFF will generate the task ID
    if provider == "stability":
        data = {
            'provider': provider,
            'input_image_asset_url': image_url,
            'model': 'fast',
            'prompt': 'high-resolution detailed image',
            'output_format': 'png'
        }
    else:  # recraft
        data = {
            'provider': provider,
            'input_image_asset_url': image_url,
            'model': 'crisp',
            'response_format': 'url'
        }
    
    response = requests.post(
        'https://api.makeit3d.io/generate/upscale',  # Real production API
        headers={
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        },
        json=data
    )
    
    if response.status_code != 200:
        raise Exception(f"Upscale submission failed: {response.status_code} - {response.text}")
    
    # 2. BFF returns the task ID it generated
    result = response.json()
    task_id = result['task_id']  # BFF-generated task ID
    
    print(f"Upscale job submitted with BFF-generated task ID: {task_id}")
    
    # 3. Poll using the BFF-provided task ID
    while True:
        status_response = requests.get(
            f'https://api.makeit3d.io/tasks/{task_id}/status',  # Real production API
            headers={'X-API-Key': api_key}
        )
        
        if status_response.status_code != 200:
            raise Exception(f"Status check failed: {status_response.status_code} - {status_response.text}")
        
        task_result_data = status_response.json()
        status = task_result_data.get('status')
        
        print(f"Status: {status}")
        
        if status == 'complete':
            print("✅ Upscaling complete!")
            return task_result_data.get('asset_url')
        elif status == 'failed':
            raise Exception(f"Upscaling failed: {task_result_data.get('error', 'Unknown error')}")
        
        time.sleep(2)

def downscale_image(image_url, api_key, max_size_mb=0.5, aspect_ratio_mode="original", output_format="original"):
    """
    Downscale an image using the MakeIt3D API.
    
    Args:
        image_url (str): URL to the source image
        api_key (str): Your MakeIt3D API key
        max_size_mb (float): Target file size in megabytes
        aspect_ratio_mode (str): "original" or "square"
        output_format (str): "original", "jpeg", "png", or "webp"
    
    Returns:
        str: URL to the downscaled image
    """
    # 1. Submit downscale job - BFF will generate the task ID
    data = {
        'input_image_asset_url': image_url,
        'max_size_mb': max_size_mb,
        'aspect_ratio_mode': aspect_ratio_mode,
        'output_format': output_format
    }
    
    response = requests.post(
        'https://api.makeit3d.io/generate/downscale',  # Real production API
        headers={
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        },
        json=data
    )
    
    if response.status_code != 200:
        raise Exception(f"Downscale submission failed: {response.status_code} - {response.text}")
    
    # 2. BFF returns the task ID it generated
    result = response.json()
    task_id = result['task_id']  # BFF-generated task ID
    
    print(f"Downscale job submitted with BFF-generated task ID: {task_id}")
    
    # 3. Poll using the BFF-provided task ID
    while True:
        status_response = requests.get(
            f'https://api.makeit3d.io/tasks/{task_id}/status',  # Real production API
            headers={'X-API-Key': api_key}
        )
        
        if status_response.status_code != 200:
            raise Exception(f"Status check failed: {status_response.status_code} - {status_response.text}")
        
        task_result_data = status_response.json()
        status = task_result_data.get('status')
        
        print(f"Status: {status}")
        
        if status == 'complete':
            print("✅ Downscaling complete!")
            # Note: Downscale returns 'image_url' instead of 'asset_url'
            return task_result_data.get('asset_url') or task_result_data.get('image_url')
        elif status == 'failed':
            raise Exception(f"Downscaling failed: {task_result_data.get('error', 'Unknown error')}")
        
        time.sleep(2)

# Example usage
if __name__ == "__main__":
    # Use the test API key from Supabase
    TEST_API_KEY = "makeit3d_test_sk_dev_001"  # Real test key from production DB
    
    # Option: Register for production API key (uncomment to use)
    """
    try:
        registration_response = register_api_key(
            verification_secret="YOUR_SECRET_KEY",  # Get this from MakeIt3D
            tenant_type="supabase_app",
            tenant_identifier="my-photo-app",
            tenant_name="My Photo Editor App",
            metadata={
                "app_version": "1.0.0",
                "developer": "Your Company",
                "description": "Photo editing application"
            }
        )
        
        print("✅ Registration successful!")
        print(f"API Key: {registration_response['api_key']}")
        print(f"Tenant ID: {registration_response['tenant_id']}")
        
        # Use the production API key
        api_key = registration_response['api_key']
        
    except Exception as e:
        print(f"❌ Registration failed: {e}")
        # Fall back to test key
        api_key = TEST_API_KEY
    """
    
    # Use test API key for this example
    api_key = TEST_API_KEY
    
    # Test image URL (publicly accessible)
    test_image_url = "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg"
    
    print("🔄 Starting complete image processing workflow...")
    print(f"📸 Original image: {test_image_url}")
    print()
    
    try:
        # Step 1: Remove background
        print("1️⃣ REMOVE BACKGROUND")
        print("🚀 Starting background removal...")
        bg_removed_url = remove_background(test_image_url, api_key, provider="stability")
        print(f"✅ Background removed! URL: {bg_removed_url}")
        print()
        
        # Step 2: Upscale the result
        print("2️⃣ UPSCALE IMAGE")
        print("🚀 Starting upscaling...")
        upscaled_url = upscale_image(bg_removed_url, api_key, provider="stability")
        print(f"✅ Image upscaled! URL: {upscaled_url}")
        print()
        
        # Step 3: Downscale for optimization
        print("3️⃣ DOWNSCALE IMAGE")
        print("🚀 Starting downscaling...")
        final_url = downscale_image(upscaled_url, api_key, max_size_mb=0.8, aspect_ratio_mode="original", output_format="png")
        print(f"✅ Image downscaled! URL: {final_url}")
        print()
        
        # Summary
        print("🎉 WORKFLOW COMPLETE!")
        print("📋 Processing Summary:")
        print(f"   • Original image: {test_image_url}")
        print(f"   • Background removed: {bg_removed_url}")
        print(f"   • Upscaled: {upscaled_url}")
        print(f"   • Final optimized: {final_url}")
        print("📥 Download any of the processed images before URLs expire (1 hour for private buckets)")
        
    except Exception as e:
        print(f"❌ Error during processing: {e}")