import requests
import os
import time
from dotenv import load_dotenv
from io import BytesIO

def test_recraft_upscale():
    """
    Tests the Recraft AI Crisp Upscale functionality.
    Downloads an input image, sends it to the API to increase image resolution,
    making the image sharper and cleaner, and saves the resulting upscaled image with execution timings.
    
    Features:
    - Enhances image resolution using 'crisp upscale' tool
    - Increases image resolution while making images sharper and cleaner
    - Focuses on clarity and sharpness improvements
    """
    load_dotenv()
    timings = []
    total_start_time = time.time()

    api_key = os.getenv("RECRAFT_API_KEY")
    if not api_key:
        raise ValueError("RECRAFT_API_KEY not found in environment variables. Make sure it's in your .env file.")

    # Configuration - modify these as needed
    api_endpoint = "https://external.api.recraft.ai/v1/images/crispUpscale"
    
    # Input image URL - using a smaller image that will benefit from upscaling
    input_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy.jpg"
    
    # Parameters
    response_format = "url"  # Options: url, b64_json
    
    output_dir = "tests/outputs"
    output_filename = "recraft_crisp_upscale_output.png"
    output_path = os.path.join(output_dir, output_filename)

    os.makedirs(output_dir, exist_ok=True)

    # 1. Download input image
    step_start_time = time.time()
    print(f"Downloading input image from {input_image_url}...")
    try:
        image_response = requests.get(input_image_url)
        image_response.raise_for_status()
        input_image_bytes = image_response.content
        print("Input image downloaded successfully.")
        timings.append(["Download Input Image", f"{time.time() - step_start_time:.2f}"])
    except requests.exceptions.RequestException as e:
        timings.append(["Download Input Image", f"Failed: {e}"])
        raise Exception(f"Failed to download input image: {e}")

    # 2. API Request
    step_start_time = time.time()
    print(f"Sending request to Recraft AI Crisp Upscale: {api_endpoint}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        # Content-Type will be set automatically by requests for multipart/form-data
    }
    
    files = {
        "file": ("input_image.jpg", BytesIO(input_image_bytes), "image/jpeg")
    }
    
    data = {
        "response_format": response_format
    }

    try:
        response = requests.post(api_endpoint, headers=headers, files=files, data=data)
        timings.append(["API Call", f"{time.time() - step_start_time:.2f}"])
        
        if response.status_code == 200:
            print("Crisp upscaling successful!")
            response_data = response.json()
            
            # Get the image URL from response
            if response_data.get("image") and response_data["image"].get("url"):
                image_url = response_data["image"]["url"]
                print(f"Crisp upscaled image URL: {image_url}")
                
                # Download the upscaled image
                step_start_time = time.time()
                print("Downloading crisp upscaled image...")
                image_download_response = requests.get(image_url)
                image_download_response.raise_for_status()
                upscaled_image_bytes = image_download_response.content
                timings.append(["Download Upscaled Image", f"{time.time() - step_start_time:.2f}"])
            else:
                raise Exception("No crisp upscaled image URL found in response")
        else:
            response.raise_for_status()

    except requests.exceptions.HTTPError as e:
        error_message = f"API Error: {e.response.status_code}"
        try:
            error_details = e.response.json()
            error_message += f" - {error_details}"
        except requests.exceptions.JSONDecodeError:
            error_message += f" - {e.response.text}"
        timings.append(["API Call", f"Failed: {error_message}"])
        raise Exception(error_message)
    except Exception as e:
        timings.append(["API Call", f"Failed: {e}"])
        raise Exception(f"Error during API call: {e}")

    # 3. Save upscaled image
    step_start_time = time.time()
    print(f"Saving crisp upscaled image to {output_path}...")
    try:
        with open(output_path, 'wb') as f:
            f.write(upscaled_image_bytes)
        print(f"Crisp upscaled image saved successfully to {output_path}")
        timings.append(["Save Upscaled Image", f"{time.time() - step_start_time:.2f}"])
    except Exception as e:
        timings.append(["Save Upscaled Image", f"Failed: {e}"])
        raise Exception(f"Failed to save crisp upscaled image: {e}")

    total_duration = time.time() - total_start_time
    timings.append(["Total Execution Time", f"{total_duration:.2f}"])
    
    print("\n--- Execution Timings ---")
    print(f"{'Step':<40} {'Duration (s)':<15}")
    print("-" * 55)
    for step, duration in timings:
        print(f"{step:<40} {duration:<15}")
    
    print(f"\n--- Configuration Used ---")
    print(f"Model: Recraft Crisp Upscale")
    print(f"Endpoint: {api_endpoint}")
    print(f"Input Image: {input_image_url}")
    print(f"Response Format: {response_format}")
    print(f"Output File: {output_path}")
    
    # Basic image verification
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        print(f"Output file size: {file_size:,} bytes")
        if file_size > 0:
            print("✅ Crisp upscaled image saved successfully!")
        else:
            print("❌ Crisp upscaled image file is empty")
    else:
        print("❌ Crisp upscaled image file was not created")

if __name__ == "__main__":
    print("Running Recraft AI Crisp Upscale test...")
    try:
        test_recraft_upscale()
        print("\nTest completed successfully.")
    except Exception as e:
        print(f"\nTest failed: {e}")
        # If timings were partially collected before failure, print them
        if 'timings' in locals() and timings:
            print("\n--- Partial Execution Timings ---")
            print(f"{'Step':<40} {'Duration (s)':<15}")
            print("-" * 55)
            for step, duration in timings:
                print(f"{step:<40} {duration:<15}") 