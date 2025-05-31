import requests
import os
import time
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image

def test_recraft_image_to_image():
    """
    Tests the Recraft AI image-to-image functionality.
    Downloads an input image, sends it to the API with a prompt and configuration,
    and saves the resulting image with execution timings.
    Optionally removes the background as a second API call.
    """
    load_dotenv()
    timings = []
    total_start_time = time.time()

    api_key = os.getenv("RECRAFT_API_KEY")
    if not api_key:
        raise ValueError("RECRAFT_API_KEY not found in environment variables. Make sure it's in your .env file.")

    # Configuration - modify these as needed
    api_endpoint = "https://external.api.recraft.ai/v1/images/imageToImage"
    
    # Input image URL (same as Stability tests)
    input_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept"
    
    # Parameters
    prompt_text = "cat with blue body standing and large feather wings on its back, no background"
    negative_prompt = "blurry, low quality, distorted"
    strength = 0.2  # Range: 0.0 to 1.0 (0 = almost identical, 1 = very different)
    n = 1  # Number of images to generate (1-6)
    style = "realistic_image"  # Options: realistic_image, digital_illustration, vector_illustration, realistic_image, etc.
    substyle = None  # Optional substyle
    model = "recraftv3"  # Only recraftv3 is supported
    response_format = "url"  # Options: url, b64_json
    
    # Background removal option
    remove_background = True  # Set to True to remove background after generation
    
    output_dir = "tests/outputs"
    output_filename = "recraft_image_to_image_output.png"
    output_path = os.path.join(output_dir, output_filename)
    
    # Background removal output path
    bg_removed_filename = "recraft_image_to_image_no_bg.png"
    bg_removed_path = os.path.join(output_dir, bg_removed_filename)

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
    print(f"Sending request to Recraft AI image-to-image endpoint: {api_endpoint}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        # Content-Type will be set automatically by requests for multipart/form-data
    }
    
    files = {
        "image": ("input_image.jpg", BytesIO(input_image_bytes), "image/jpeg")
    }
    
    data = {
        "prompt": prompt_text,
        "strength": strength,
        "n": n,
        "style": style,
        "model": model,
        "response_format": response_format
    }
    
    if negative_prompt:
        data["negative_prompt"] = negative_prompt
    if substyle:
        data["substyle"] = substyle

    try:
        response = requests.post(api_endpoint, headers=headers, files=files, data=data)
        timings.append(["API Call", f"{time.time() - step_start_time:.2f}"])
        
        if response.status_code == 200:
            print("Generation successful!")
            response_data = response.json()
            
            # Get the image URL from response
            if response_data.get("data") and len(response_data["data"]) > 0:
                image_url = response_data["data"][0]["url"]
                print(f"Generated image URL: {image_url}")
                
                # Download the generated image
                step_start_time = time.time()
                print("Downloading generated image...")
                image_download_response = requests.get(image_url)
                image_download_response.raise_for_status()
                final_image_content = image_download_response.content
                timings.append(["Download Generated Image", f"{time.time() - step_start_time:.2f}"])
            else:
                raise Exception("No image data found in response")
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

    # 3. Save image
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

    # 4. Remove background (optional)
    if remove_background and final_image_content:
        step_start_time = time.time()
        print(f"Removing background from generated image...")
        
        bg_removal_endpoint = "https://external.api.recraft.ai/v1/images/removeBackground"
        bg_headers = {
            "Authorization": f"Bearer {api_key}",
        }
        
        bg_files = {
            "file": ("generated_image.png", BytesIO(final_image_content), "image/png")
        }
        bg_data = {
            "response_format": "url"
        }
        
        try:
            bg_response = requests.post(bg_removal_endpoint, headers=bg_headers, files=bg_files, data=bg_data)
            timings.append(["Remove Background", f"{time.time() - step_start_time:.2f}"])
            
            if bg_response.status_code == 200:
                print("Background removal successful!")
                bg_response_data = bg_response.json()
                
                if bg_response_data.get("image") and bg_response_data["image"].get("url"):
                    bg_removed_url = bg_response_data["image"]["url"]
                    print(f"Background-removed image URL: {bg_removed_url}")
                    
                    # Download the background-removed image
                    step_start_time = time.time()
                    print("Downloading background-removed image...")
                    bg_download_response = requests.get(bg_removed_url)
                    bg_download_response.raise_for_status()
                    bg_removed_content = bg_download_response.content
                    
                    # Save background-removed image
                    print(f"Saving background-removed image to {bg_removed_path}...")
                    with open(bg_removed_path, 'wb') as f:
                        f.write(bg_removed_content)
                    print(f"Background-removed image saved successfully to {bg_removed_path}")
                    timings.append(["Save BG-Removed Image", f"{time.time() - step_start_time:.2f}"])
                else:
                    raise Exception("No background-removed image URL found in response")
            else:
                bg_response.raise_for_status()
                
        except requests.exceptions.HTTPError as e:
            error_message = f"Background Removal API Error: {e.response.status_code}"
            try:
                error_details = e.response.json()
                error_message += f" - {error_details}"
            except requests.exceptions.JSONDecodeError:
                error_message += f" - {e.response.text}"
            timings.append(["Remove Background", f"Failed: {error_message}"])
            print(f"Background removal failed: {error_message}")
        except Exception as e:
            timings.append(["Remove Background", f"Failed: {e}"])
            print(f"Error during background removal: {e}")

    total_duration = time.time() - total_start_time
    timings.append(["Total Execution Time", f"{total_duration:.2f}"])
    
    print("\n--- Execution Timings ---")
    print(f"{'Step':<40} {'Duration (s)':<15}")
    print("-" * 55)
    for step, duration in timings:
        print(f"{step:<40} {duration:<15}")
    
    print(f"\n--- Configuration Used ---")
    print(f"Endpoint: Recraft Image-to-Image")
    print(f"Prompt: {prompt_text}")
    print(f"Negative Prompt: {negative_prompt}")
    print(f"Strength: {strength}")
    print(f"Style: {style}")
    print(f"Substyle: {substyle or 'None'}")
    print(f"Model: {model}")
    print(f"Number of Images: {n}")
    print(f"Response Format: {response_format}")
    print(f"Remove Background: {remove_background}")

if __name__ == "__main__":
    print("Running Recraft AI image-to-image test...")
    try:
        test_recraft_image_to_image()
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