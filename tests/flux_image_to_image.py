import requests
import os
import time
import base64
from dotenv import load_dotenv
from io import BytesIO

def test_flux_image_to_image():
    """
    Tests the Flux Kontext Pro image-to-image functionality using direct API.
    Downloads an input image, converts to base64, sends it to the API with a prompt,
    polls for completion, and saves the resulting image with execution timings.
    """
    load_dotenv()
    timings = []
    total_start_time = time.time()

    api_key = os.getenv("FLUX_API_KEY")
    if not api_key:
        raise ValueError("FLUX_API_KEY not found in environment variables. Make sure it's in your .env file.")

    # Configuration - modify these as needed
    api_endpoint = "https://api.bfl.ai/v1/flux-kontext-pro"
    
    # Input image URL (same as other tests)
    input_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept"
    
    # Parameters - keeping the same prompt as requested
    prompt_text = "change orange fur to light blue, and black stripes to green"
    aspect_ratio = "1:1"  # Options: between 21:9 and 9:21
    output_format = "png"  # Options: jpeg, png
    seed = None  # Optional: set for reproducible generation
    safety_tolerance = 2  # Range: 0-6, 0 most strict, 6 least strict
    prompt_upsampling = False  # Whether to upsample the prompt
    
    output_dir = "tests/outputs"
    output_filename = "flux_kontext_pro_output.png"
    output_path = os.path.join(output_dir, output_filename)

    os.makedirs(output_dir, exist_ok=True)

    # 1. Download and convert input image to base64
    step_start_time = time.time()
    print(f"Downloading input image from {input_image_url}...")
    try:
        image_response = requests.get(input_image_url)
        image_response.raise_for_status()
        input_image_bytes = image_response.content
        
        # Convert to base64
        input_image_b64 = base64.b64encode(input_image_bytes).decode('utf-8')
        print("Input image downloaded and converted to base64 successfully.")
        timings.append(["Download & Convert Input Image", f"{time.time() - step_start_time:.2f}"])
    except requests.exceptions.RequestException as e:
        timings.append(["Download Input Image", f"Failed: {e}"])
        raise Exception(f"Failed to download input image: {e}")

    # 2. API Request
    step_start_time = time.time()
    print(f"Sending request to Flux Kontext Pro API: {api_endpoint}...")
    
    headers = {
        "x-key": api_key,
        "Content-Type": "application/json"
    }
    
    # Prepare payload
    payload = {
        "prompt": prompt_text,
        "input_image": input_image_b64,
        "aspect_ratio": aspect_ratio,
        "output_format": output_format,
        "safety_tolerance": safety_tolerance,
        "prompt_upsampling": prompt_upsampling
    }
    
    # Add seed if specified
    if seed is not None:
        payload["seed"] = seed

    try:
        response = requests.post(api_endpoint, headers=headers, json=payload)
        timings.append(["API Call", f"{time.time() - step_start_time:.2f}"])
        
        if response.status_code == 200:
            print("Generation request submitted successfully!")
            response_data = response.json()
            
            task_id = response_data.get("id")
            polling_url = response_data.get("polling_url")
            
            if not task_id or not polling_url:
                raise Exception("Missing task ID or polling URL in response")
                
            print(f"Task ID: {task_id}")
            print(f"Polling URL: {polling_url}")
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

    # 3. Poll for completion
    step_start_time = time.time()
    print("Polling for task completion...")
    
    max_polls = 60  # Maximum number of polls
    poll_interval = 5  # Seconds between polls
    
    for poll_count in range(max_polls):
        try:
            poll_response = requests.get(polling_url, headers={"x-key": api_key})
            poll_response.raise_for_status()
            poll_data = poll_response.json()
            
            status = poll_data.get("status")
            print(f"Poll {poll_count + 1}: Status = {status}")
            
            if status == "Ready":
                # Task completed successfully
                result = poll_data.get("result")
                if result and result.get("sample"):
                    image_url = result["sample"]
                    print(f"Generation completed! Image URL: {image_url}")
                    timings.append(["Polling", f"{time.time() - step_start_time:.2f}"])
                    break
                else:
                    raise Exception("No image URL found in completed result")
                    
            elif status in ["Error", "Failed"]:
                error_msg = poll_data.get("error", "Unknown error")
                raise Exception(f"Generation failed: {error_msg}")
                
            elif status in ["Pending", "Running"]:
                # Still processing, continue polling
                time.sleep(poll_interval)
                continue
            else:
                print(f"Unknown status: {status}, continuing to poll...")
                time.sleep(poll_interval)
                continue
                
        except requests.exceptions.RequestException as e:
            print(f"Polling error: {e}")
            time.sleep(poll_interval)
            continue
    else:
        # Max polls reached without completion
        timings.append(["Polling", f"Timeout after {time.time() - step_start_time:.2f}"])
        raise Exception(f"Task did not complete within {max_polls} polls")

    # 4. Download and save the generated image
    step_start_time = time.time()
    print("Downloading generated image...")
    try:
        image_download_response = requests.get(image_url)
        image_download_response.raise_for_status()
        final_image_content = image_download_response.content
        timings.append(["Download Generated Image", f"{time.time() - step_start_time:.2f}"])
        
        # Save the image
        step_start_time = time.time()
        print(f"Saving image to {output_path}...")
        with open(output_path, 'wb') as f:
            f.write(final_image_content)
        print(f"Image saved successfully to {output_path}")
        timings.append(["Save Image", f"{time.time() - step_start_time:.2f}"])
        
    except requests.exceptions.RequestException as e:
        timings.append(["Download Generated Image", f"Failed: {e}"])
        raise Exception(f"Failed to download generated image: {e}")
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
    print(f"Endpoint: Flux Kontext Pro (Direct API)")
    print(f"Prompt: {prompt_text}")
    print(f"Input Image: {input_image_url}")
    print(f"Aspect Ratio: {aspect_ratio}")
    print(f"Output Format: {output_format}")
    print(f"Seed: {seed or 'Random'}")
    print(f"Safety Tolerance: {safety_tolerance}")
    print(f"Prompt Upsampling: {prompt_upsampling}")

if __name__ == "__main__":
    print("Running Flux Kontext Pro image-to-image test...")
    try:
        test_flux_image_to_image()
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