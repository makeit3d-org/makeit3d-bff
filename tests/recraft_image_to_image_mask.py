import requests
import os
import time
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image

def convert_mask_to_binary(mask_image_bytes):
    """
    Convert a mask image to binary format (only 0 or 255 pixel values) as required by Recraft.
    
    Args:
        mask_image_bytes: Raw image bytes of the mask
        
    Returns:
        bytes: Processed mask image bytes in binary format
        
    Raises:
        Exception: If mask conversion fails
    """
    try:
        print("Converting mask to binary format (black/white only)...")
        mask_image = Image.open(BytesIO(mask_image_bytes))
        
        # Convert to grayscale if not already
        if mask_image.mode != 'L':
            mask_image = mask_image.convert('L')
            print(f"Converted mask from {mask_image.mode} mode to grayscale")
        else:
            print("Mask is already in grayscale mode")
        
        # Convert to binary (only 0 or 255 values) using threshold
        # Pixels below 128 become 0 (black), pixels 128+ become 255 (white)
        threshold = 128
        mask_array = mask_image.point(lambda x: 0 if x < threshold else 255, mode='L')
        print(f"Applied binary threshold at {threshold} - pixels below become 0 (black), above become 255 (white)")
        
        # Save the binary mask to bytes
        mask_buffer = BytesIO()
        mask_array.save(mask_buffer, format='PNG')
        return mask_buffer.getvalue()
        
    except Exception as e:
        raise Exception(f"Failed to convert mask to binary format: {e}")

def test_recraft_image_to_image_mask():
    """
    Tests the Recraft AI inpainting functionality.
    Downloads an input image and mask, sends them to the API to intelligently modify
    specified areas, and saves the resulting image with execution timings.
    
    Features:
    - Intelligently modify images by filling in or replacing specified areas
    - Uses mask to control inpainting areas
    - White pixels = areas to inpaint, black pixels = areas to keep unchanged
    - Optionally removes background as a second API call
    """
    load_dotenv()
    timings = []
    total_start_time = time.time()

    api_key = os.getenv("RECRAFT_API_KEY")
    if not api_key:
        raise ValueError("RECRAFT_API_KEY not found in environment variables. Make sure it's in your .env file.")

    # Configuration - modify these as needed
    api_endpoint = "https://external.api.recraft.ai/v1/images/inpaint"
    
    # Input URLs
    input_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept"
    mask_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept-mask.png"
    
    # Parameters
    prompt = "add large colorful feathery wings with rainbow colors"
    negative_prompt = "blurry, low quality, distorted, deformed"
    n = 1  # Number of images to generate (1-6)
    style = "realistic_image"  # Options: realistic_image, digital_illustration, vector_illustration, etc.
    substyle = None  # Optional substyle
    model = "recraftv3"  # Only recraftv3 is supported
    response_format = "url"  # Options: url, b64_json
    
    # Background removal configuration
    remove_background = True  # Set to False to skip background removal
    
    output_dir = "tests/outputs"
    output_filename = "recraft_inpaint_cat_output.png"
    output_path = os.path.join(output_dir, output_filename)
    
    # Background removal output path
    bg_removed_filename = "recraft_inpaint_cat_output_no_bg.png"
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

    # 2. Download mask image
    step_start_time = time.time()
    print(f"Downloading mask image from {mask_image_url}...")
    try:
        mask_response = requests.get(mask_image_url)
        mask_response.raise_for_status()
        mask_image_bytes = mask_response.content
        print("Mask image downloaded successfully.")
        
        # Convert mask to binary format required by Recraft
        mask_image_bytes = convert_mask_to_binary(mask_image_bytes)
        
        timings.append(["Download & Convert Mask", f"{time.time() - step_start_time:.2f}"])
    except requests.exceptions.RequestException as e:
        timings.append(["Download Mask Image", f"Failed: {e}"])
        raise Exception(f"Failed to download mask image: {e}")
    except Exception as e:
        timings.append(["Convert Mask", f"Failed: {e}"])
        raise Exception(f"Failed to convert mask to binary format: {e}")

    # 3. API Request
    step_start_time = time.time()
    print(f"Sending request to Recraft AI Inpaint: {api_endpoint}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        # Content-Type will be set automatically by requests for multipart/form-data
    }
    
    files = {
        "image": ("sketch_cat_concept.png", BytesIO(input_image_bytes), "image/png"),
        "mask": ("sketch_cat_concept_mask.png", BytesIO(mask_image_bytes), "image/png")
    }
    
    data = {
        "prompt": prompt,
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
            print("Inpainting successful!")
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
                generated_image_bytes = image_download_response.content
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

    # 4. Save generated image
    step_start_time = time.time()
    print(f"Saving generated image to {output_path}...")
    try:
        with open(output_path, 'wb') as f:
            f.write(generated_image_bytes)
        print(f"Generated image saved successfully to {output_path}")
        timings.append(["Save Generated Image", f"{time.time() - step_start_time:.2f}"])
    except Exception as e:
        timings.append(["Save Generated Image", f"Failed: {e}"])
        raise Exception(f"Failed to save generated image: {e}")

    # 5. Background removal (optional)
    if remove_background:
        step_start_time = time.time()
        print("Removing background from generated image...")
        
        bg_removal_endpoint = "https://external.api.recraft.ai/v1/images/removeBackground"
        bg_headers = {
            "Authorization": f"Bearer {api_key}",
        }
        
        bg_files = {
            "file": ("generated_image.png", BytesIO(generated_image_bytes), "image/png")
        }
        bg_data = {
            "response_format": "url"
        }
        
        try:
            bg_response = requests.post(bg_removal_endpoint, headers=bg_headers, files=bg_files, data=bg_data)
            
            if bg_response.status_code == 200:
                print("Background removal successful!")
                bg_response_data = bg_response.json()
                
                if bg_response_data.get("image") and bg_response_data["image"].get("url"):
                    bg_removed_url = bg_response_data["image"]["url"]
                    print(f"Background-removed image URL: {bg_removed_url}")
                    
                    # Download the background-removed image
                    print("Downloading background-removed image...")
                    bg_download_response = requests.get(bg_removed_url)
                    bg_download_response.raise_for_status()
                    bg_removed_bytes = bg_download_response.content
                    
                    # Save background-removed image
                    with open(bg_removed_path, 'wb') as f:
                        f.write(bg_removed_bytes)
                    print(f"Background-removed image saved to {bg_removed_path}")
                    timings.append(["Background Removal", f"{time.time() - step_start_time:.2f}"])
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
            timings.append(["Background Removal", f"Failed: {error_message}"])
            print(f"Warning: Background removal failed: {error_message}")
        except Exception as e:
            timings.append(["Background Removal", f"Failed: {e}"])
            print(f"Warning: Background removal failed: {e}")

    total_duration = time.time() - total_start_time
    timings.append(["Total Execution Time", f"{total_duration:.2f}"])
    
    print("\n--- Execution Timings ---")
    print(f"{'Step':<40} {'Duration (s)':<15}")
    print("-" * 55)
    for step, duration in timings:
        print(f"{step:<40} {duration:<15}")
    
    print(f"\n--- Configuration Used ---")
    print(f"Model: Recraft Inpaint")
    print(f"Endpoint: {api_endpoint}")
    print(f"Input Image: {input_image_url}")
    print(f"Mask Image: {mask_image_url}")
    print(f"Prompt: {prompt}")
    print(f"Negative Prompt: {negative_prompt}")
    print(f"Number of Images: {n}")
    print(f"Style: {style}")
    print(f"Substyle: {substyle or 'None'}")
    print(f"Model: {model}")
    print(f"Response Format: {response_format}")
    print(f"Remove Background: {remove_background}")

if __name__ == "__main__":
    print("Running Recraft AI Inpaint test...")
    try:
        test_recraft_image_to_image_mask()
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