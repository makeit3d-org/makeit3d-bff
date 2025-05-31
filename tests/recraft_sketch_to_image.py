import requests
import os
import time
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image

def create_custom_style(api_key, style_reference_url, base_style="digital_illustration"):
    """
    Creates a custom style using a reference image.
    
    Args:
        api_key: Recraft API key
        style_reference_url: URL of the reference image
        base_style: Base style to use (default: digital_illustration)
        
    Returns:
        str: Style ID if successful
        
    Raises:
        Exception: If style creation fails
    """
    print(f"Creating custom style using reference: {style_reference_url}")
    
    # Download the reference image
    try:
        ref_response = requests.get(style_reference_url)
        ref_response.raise_for_status()
        ref_image_bytes = ref_response.content
        print("Reference image downloaded successfully.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to download reference image: {e}")
    
    # Create style via API
    style_endpoint = "https://external.api.recraft.ai/v1/styles"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    files = {
        "file1": ("reference.png", BytesIO(ref_image_bytes), "image/png")
    }
    
    data = {
        "style": base_style
    }
    
    try:
        response = requests.post(style_endpoint, headers=headers, files=files, data=data)
        
        if response.status_code == 200:
            response_data = response.json()
            style_id = response_data.get("id")
            if style_id:
                print(f"Custom style created successfully! Style ID: {style_id}")
                return style_id
            else:
                raise Exception("No style ID returned in response")
        else:
            response.raise_for_status()
            
    except requests.exceptions.HTTPError as e:
        error_message = f"Style Creation API Error: {e.response.status_code}"
        try:
            error_details = e.response.json()
            error_message += f" - {error_details}"
        except requests.exceptions.JSONDecodeError:
            error_message += f" - {e.response.text}"
        raise Exception(error_message)
    except Exception as e:
        raise Exception(f"Error during style creation: {e}")

def test_recraft_sketch_to_image():
    """
    Tests the Recraft AI sketch-to-image functionality using the image-to-image endpoint.
    First creates a custom style using a reference image, then downloads a sketch image, 
    sends it to the API with the custom style and prompt, and saves the resulting image 
    with execution timings. Optionally removes the background as a second API call.
    """
    load_dotenv()
    timings = []
    total_start_time = time.time()

    api_key = os.getenv("RECRAFT_API_KEY")
    if not api_key:
        raise ValueError("RECRAFT_API_KEY not found in environment variables. Make sure it's in your .env file.")

    # Configuration - modify these as needed
    api_endpoint = "https://external.api.recraft.ai/v1/images/imageToImage"
    
    # Input URLs
    sketch_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat2.png"
    style_reference_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//portrait-boy-front-concept.png"
    
    # Parameters
    prompt_text = "3D model of a cat with a crown and wings, no background"
    negative_prompt = "blurry, low quality, distorted, flat, 2D"
    strength = 0.6  # Range: 0.0 to 1.0 (0 = almost identical, 1 = very different) - higher for sketch transformation
    n = 1  # Number of images to generate (1-6)
    base_style = "realistic_image"  # Base style for 3D model-like appearance
    model = "recraftv3"  # Only recraftv3 is supported
    response_format = "url"  # Options: url, b64_json
    
    # Style configuration - set existing_style_id to use a previously created style
    existing_style_id = None  # Set this to your existing style ID to skip creation (e.g., "229b2a75-05e4-4580-85f9-b47ee521a00d")
    create_new_style = existing_style_id is None  # Will create new style only if existing_style_id is None
    
    # Background removal option
    remove_background = False  # Set to True to remove background after generation
    
    output_dir = "tests/outputs"
    output_filename = "recraft_sketch_to_image_output.png"
    output_path = os.path.join(output_dir, output_filename)
    
    # Background removal output path
    bg_removed_filename = "recraft_sketch_to_image_no_bg.png"
    bg_removed_path = os.path.join(output_dir, bg_removed_filename)

    os.makedirs(output_dir, exist_ok=True)

    # 1. Get or create custom style
    if create_new_style:
        step_start_time = time.time()
        try:
            custom_style_id = create_custom_style(api_key, style_reference_url, base_style)
            timings.append(["Create Custom Style", f"{time.time() - step_start_time:.2f}"])
            print(f"💡 Save this Style ID for future use: {custom_style_id}")
            print("💡 Set existing_style_id = \"{custom_style_id}\" in the script to reuse this style and save credits!")
        except Exception as e:
            timings.append(["Create Custom Style", f"Failed: {e}"])
            raise Exception(f"Failed to create custom style: {e}")
    else:
        custom_style_id = existing_style_id
        print(f"Using existing custom style ID: {custom_style_id}")
        timings.append(["Use Existing Style", "0.00 (no API call needed)"])

    # 2. Download sketch image
    step_start_time = time.time()
    print(f"Downloading sketch image from {sketch_image_url}...")
    try:
        image_response = requests.get(sketch_image_url)
        image_response.raise_for_status()
        input_image_bytes = image_response.content
        print("Sketch image downloaded successfully.")
        timings.append(["Download Sketch Image", f"{time.time() - step_start_time:.2f}"])
    except requests.exceptions.RequestException as e:
        timings.append(["Download Sketch Image", f"Failed: {e}"])
        raise Exception(f"Failed to download sketch image: {e}")

    # 3. API Request
    step_start_time = time.time()
    print(f"Sending request to Recraft AI image-to-image endpoint: {api_endpoint}...")
    print(f"Using custom style ID: {custom_style_id}")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        # Content-Type will be set automatically by requests for multipart/form-data
    }
    
    files = {
        "image": ("sketch_cat.png", BytesIO(input_image_bytes), "image/png")
    }
    
    data = {
        "prompt": prompt_text,
        "strength": strength,
        "n": n,
        "style_id": custom_style_id,  # Use custom style instead of base style
        "model": model,
        "response_format": response_format
    }
    
    if negative_prompt:
        data["negative_prompt"] = negative_prompt

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

    # 5. Remove background (optional)
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
    print(f"Endpoint: Recraft Image-to-Image (Sketch-to-Image with Custom Style)")
    print(f"Sketch Image: {sketch_image_url}")
    if create_new_style:
        print(f"Style Reference: {style_reference_url}")
        print(f"Created New Style ID: {custom_style_id}")
    else:
        print(f"Used Existing Style ID: {custom_style_id}")
    print(f"Base Style: {base_style} (for 3D model-like appearance)")
    print(f"Prompt: {prompt_text}")
    print(f"Negative Prompt: {negative_prompt}")
    print(f"Strength: {strength}")
    print(f"Model: {model}")
    print(f"Number of Images: {n}")
    print(f"Response Format: {response_format}")
    print(f"Remove Background: {remove_background}")
    
    # Cost breakdown
    total_cost_units = 0
    total_cost_usd = 0.0
    
    if create_new_style:
        print(f"Style Creation Cost: 40 API Units ($0.04)")
        total_cost_units += 40
        total_cost_usd += 0.04
    else:
        print(f"Style Creation Cost: 0 API Units ($0.00) - Used existing style")
    
    print(f"Image Generation Cost: 40 API Units ($0.04)")
    total_cost_units += 40
    total_cost_usd += 0.04
    
    if remove_background:
        print(f"Background Removal Cost: 10 API Units ($0.01)")
        total_cost_units += 10
        total_cost_usd += 0.01
    
    print(f"Total Cost: {total_cost_units} API Units (${total_cost_usd:.2f})")

if __name__ == "__main__":
    print("Running Recraft AI sketch-to-image test...")
    try:
        test_recraft_sketch_to_image()
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