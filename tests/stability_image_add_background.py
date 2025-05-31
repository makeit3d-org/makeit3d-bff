import requests
import os
import time
from dotenv import load_dotenv
from io import BytesIO
import base64

def test_replace_background_and_relight():
    """
    Tests the Stability AI Replace Background and Relight functionality.
    Downloads an input image, sends it to the API with background prompts and lighting configuration,
    and saves the resulting image with execution timings.
    This is an async API that requires polling for results.
    """
    load_dotenv()
    timings = []
    total_start_time = time.time()

    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        raise ValueError("STABILITY_API_KEY not found in environment variables. Make sure it's in your .env file.")

    # Configuration - modify these as needed
    api_endpoint = "https://api.stability.ai/v2beta/stable-image/edit/replace-background-and-relight"
    results_endpoint = "https://api.stability.ai/v2beta/results/"
    
    # Input image URL (sketch-cat-concept)
    input_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept"
    
    # Parameters for background replacement and relighting
    background_prompt = "modern living room with soft natural lighting, cozy atmosphere, minimalist furniture"
    foreground_prompt = "cute cat standing upright with blue body"
    negative_prompt = "blurry, low quality, distorted, dark, harsh shadows"
    
    # Lighting parameters
    light_source_direction = "above"  # Options: above, below, left, right
    light_source_strength = 0.7  # 0.0 to 1.0, controls brightness
    
    # Advanced parameters
    preserve_original_subject = 0.8  # 0.0 to 1.0, how much to keep original subject
    original_background_depth = 0.5  # 0.0 to 1.0, depth matching
    keep_original_background = "false"  # "true" or "false"
    
    # Output settings
    output_format = "png"  # Options: png, jpeg, webp
    seed = 0  # 0 for random
    
    output_dir = "tests/outputs"
    output_filename = f"stability_replace_background_output.{output_format}"
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

    # 2. Initial API Request (Start async job)
    step_start_time = time.time()
    print(f"Sending request to Stability AI Replace Background endpoint: {api_endpoint}...")
    
    headers = {
        "authorization": f"Bearer {api_key}",
        "accept": "image/*",  # Changed to match working example
    }
    
    files = {
        "subject_image": ("subject_image.png", BytesIO(input_image_bytes), "image/png")
    }
    
    # Simplified data to match working example - only essential parameters
    data = {
        "background_prompt": background_prompt,
        "output_format": output_format,
    }
    
    # Optional: Add foreground prompt if needed
    if foreground_prompt:
        data["foreground_prompt"] = foreground_prompt
    
    # Optional: Add negative prompt if needed  
    if negative_prompt:
        data["negative_prompt"] = negative_prompt

    # Debug output
    print(f"Request data: {data}")
    print(f"Headers: {headers}")
    print(f"Files: {list(files.keys())}")

    try:
        response = requests.post(api_endpoint, headers=headers, files=files, data=data)
        timings.append(["Initial API Call", f"{time.time() - step_start_time:.2f}"])
        
        if response.status_code == 200:
            print("Job started successfully!")
            # The API returns JSON with job ID even with accept: image/*
            try:
                job_response = response.json()
                job_id = job_response.get("id")
                if not job_id:
                    raise Exception(f"No job ID returned: {job_response}")
                print(f"Job ID: {job_id}")
            except requests.exceptions.JSONDecodeError:
                # If we can't parse JSON, maybe we got the image directly
                if response.headers.get('content-type', '').startswith('image/'):
                    print("Got image directly (synchronous response)!")
                    final_image_content = response.content
                    timings.append(["Direct Image Response", f"{time.time() - step_start_time:.2f}"])
                    # Skip polling and go straight to saving
                    job_id = "direct-response"
                else:
                    raise Exception(f"Unexpected response format: {response.headers.get('content-type')}")
        else:
            response.raise_for_status()

    except requests.exceptions.HTTPError as e:
        error_message = f"API Error: {e.response.status_code}"
        print(f"Response status: {e.response.status_code}")
        print(f"Response headers: {dict(e.response.headers)}")
        try:
            error_details = e.response.json()
            error_message += f" - {error_details}"
            print(f"Error details: {error_details}")
        except requests.exceptions.JSONDecodeError:
            error_message += f" - {e.response.text}"
            print(f"Raw error response: {e.response.text}")
        timings.append(["Initial API Call", f"Failed: {error_message}"])
        raise Exception(error_message)
    except Exception as e:
        timings.append(["Initial API Call", f"Failed: {e}"])
        raise Exception(f"Error during initial API call: {e}")

    # 3. Poll for results (skip if we got image directly)
    if job_id != "direct-response":
        step_start_time = time.time()
        print(f"Polling for results...")
        poll_headers = {
            "authorization": f"Bearer {api_key}",
            # Try without accept header first, then with image/* if needed
        }
        
        max_poll_attempts = 30  # 5 minutes with 10-second intervals
        poll_interval = 10  # seconds
        
        for attempt in range(max_poll_attempts):
            try:
                poll_url = f"{results_endpoint}{job_id}"
                print(f"Polling URL: {poll_url}")
                print(f"Poll headers: {poll_headers}")
                
                poll_response = requests.get(poll_url, headers=poll_headers)
                
                print(f"Poll response status: {poll_response.status_code}")
                print(f"Poll response headers: {dict(poll_response.headers)}")
                
                if poll_response.status_code == 200:
                    # Check if we got image bytes or JSON status
                    content_type = poll_response.headers.get('content-type', '')
                    print(f"Content type: {content_type}")
                    
                    if content_type.startswith('image/'):
                        # We got the final image
                        print("Generation completed!")
                        final_image_content = poll_response.content
                        timings.append(["Poll for Results", f"{time.time() - step_start_time:.2f}"])
                        break
                    else:
                        # Still processing, check JSON response
                        try:
                            status_response = poll_response.json()
                            status = status_response.get("status", "unknown")
                            print(f"Attempt {attempt + 1}/{max_poll_attempts}: Status = {status}")
                            
                            if status == "complete":
                                # Try again with image accept header
                                continue
                            elif status in ["failed", "error"]:
                                error_detail = status_response.get("error", "Unknown error")
                                raise Exception(f"Job failed: {error_detail}")
                                
                        except requests.exceptions.JSONDecodeError:
                            print(f"Attempt {attempt + 1}/{max_poll_attempts}: Still processing...")
                            
                elif poll_response.status_code == 202:
                    print(f"Attempt {attempt + 1}/{max_poll_attempts}: Job still processing...")
                elif poll_response.status_code == 400:
                    # Debug the 400 error
                    print(f"400 Error during polling:")
                    try:
                        error_details = poll_response.json()
                        print(f"Error details: {error_details}")
                    except requests.exceptions.JSONDecodeError:
                        print(f"Raw error response: {poll_response.text}")
                    # Continue polling in case it's a temporary issue
                    print(f"Attempt {attempt + 1}/{max_poll_attempts}: HTTP 400 - continuing...")
                else:
                    print(f"Attempt {attempt + 1}/{max_poll_attempts}: HTTP {poll_response.status_code}")
                    try:
                        error_response = poll_response.json()
                        print(f"Response body: {error_response}")
                    except:
                        print(f"Raw response: {poll_response.text}")
                    
                if attempt < max_poll_attempts - 1:
                    time.sleep(poll_interval)
            except requests.exceptions.RequestException as e:
                print(f"Polling attempt {attempt + 1} failed: {e}")
                if attempt < max_poll_attempts - 1:
                    time.sleep(poll_interval)
        else:
            timings.append(["Poll for Results", f"Failed: Timeout after {max_poll_attempts * poll_interval}s"])
            raise Exception(f"Job did not complete within {max_poll_attempts * poll_interval} seconds")
    else:
        print("Skipping polling - image was received directly.")

    # 4. Save image
    step_start_time = time.time()
    print(f"Saving image to {output_path}...")
    try:
        with open(output_path, 'wb') as f:
            f.write(final_image_content)
        print(f"Image saved successfully to {output_path}")
        timings.append(["Save Image", f"{time.time() - step_start_time:.2f}"])
    except Exception as e:
        timings.append(["Save Image", f"Failed: {e}"])
        raise Exception(f"Failed to save image: {e}")

    total_duration = time.time() - total_start_time
    timings.append(["Total Execution Time", f"{total_duration:.2f}"])
    
    print("\n--- Execution Timings ---")
    print(f"{'Step':<40} {'Duration (s)':<15}")
    print("-" * 55)
    for step, duration in timings:
        print(f"{step:<40} {duration:<15}")
    
    print(f"\n--- Configuration Used ---")
    print(f"Endpoint: Replace Background and Relight (async)")
    print(f"Background Prompt: {background_prompt}")
    print(f"Foreground Prompt: {foreground_prompt}")
    print(f"Negative Prompt: {negative_prompt}")
    print(f"Light Source Direction: {light_source_direction}")
    print(f"Light Source Strength: {light_source_strength}")
    print(f"Preserve Original Subject: {preserve_original_subject}")
    print(f"Original Background Depth: {original_background_depth}")
    print(f"Keep Original Background: {keep_original_background}")
    print(f"Output Format: {output_format}")
    print(f"Seed: {seed}")
    print(f"Job ID: {job_id}")

if __name__ == "__main__":
    print("Running Stability AI Replace Background and Relight test...")
    try:
        test_replace_background_and_relight()
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