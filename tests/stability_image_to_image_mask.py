import requests
import os
import time
from dotenv import load_dotenv
from io import BytesIO

def test_image_to_image_mask():
    """
    Tests the Stability AI Inpaint functionality.
    Downloads an input image and mask, sends them to the API to intelligently modify
    specified areas, and saves the resulting image with execution timings.
    
    Features:
    - Intelligently modify images by filling in or replacing specified areas
    - Uses mask to control inpainting strength per pixel
    - Black pixels = no inpainting, white pixels = maximum strength
    - 3 credits per generation
    """
    load_dotenv()
    timings = []
    total_start_time = time.time()

    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        raise ValueError("STABILITY_API_KEY not found in environment variables. Make sure it's in your .env file.")

    # Configuration - modify these as needed
    api_endpoint = "https://api.stability.ai/v2beta/stable-image/edit/inpaint"
    
    # Input URLs
    input_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept"
    mask_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept-mask.png"
    
    # Parameters
    prompt = "larger colorful feathery wings"
    negative_prompt = "blurry, low quality, distorted, deformed"
    grow_mask = 5  # Range: 0-100 (grows mask edges outward)
    seed = 0  # 0 for random
    output_format = "png"  # Options: jpeg, png, webp
    style_preset = None  # Options: 3d-model, analog-film, anime, cinematic, comic-book, digital-art, enhance, fantasy-art, isometric, line-art, low-poly, modeling-compound, neon-punk, origami, photographic, pixel-art, tile-texture
    
    # Background removal configuration
    remove_background = True  # Set to False to skip background removal
    
    output_dir = "tests/outputs"
    output_filename = "stability_inpaint_cat_output.png"
    output_path = os.path.join(output_dir, output_filename)
    
    # Background removal output path
    bg_removed_filename = "stability_inpaint_cat_output_no_bg.png"
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
        timings.append(["Download Mask Image", f"{time.time() - step_start_time:.2f}"])
    except requests.exceptions.RequestException as e:
        timings.append(["Download Mask Image", f"Failed: {e}"])
        raise Exception(f"Failed to download mask image: {e}")

    # 3. API Request
    step_start_time = time.time()
    print(f"Sending request to Stability AI Inpaint: {api_endpoint}...")
    
    headers = {
        "authorization": f"Bearer {api_key}",
        "accept": "image/*",
        # content-type will be automatically set by requests for multipart/form-data
    }
    
    files = {
        "image": ("sketch_cat_concept.png", BytesIO(input_image_bytes), "image/png"),
        "mask": ("sketch_cat_concept_mask.png", BytesIO(mask_image_bytes), "image/png")
    }
    
    data = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "grow_mask": str(grow_mask),
        "seed": str(seed),
        "output_format": output_format
    }
    
    # Add style_preset parameter only if it's not None
    if style_preset is not None:
        data["style_preset"] = style_preset

    try:
        response = requests.post(api_endpoint, headers=headers, files=files, data=data)
        timings.append(["API Call", f"{time.time() - step_start_time:.2f}"])
        
        if response.status_code == 200:
            print("Inpainting successful!")
            generated_image_bytes = response.content
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
        
        bg_removal_endpoint = "https://api.stability.ai/v2beta/stable-image/edit/remove-background"
        bg_headers = {
            "authorization": f"Bearer {api_key}",
            "accept": "image/*"
        }
        
        bg_files = {
            "image": ("generated_image.png", BytesIO(generated_image_bytes), "image/png")
        }
        
        try:
            bg_response = requests.post(bg_removal_endpoint, headers=bg_headers, files=bg_files)
            
            if bg_response.status_code == 200:
                print("Background removal successful!")
                bg_removed_bytes = bg_response.content
                
                # Save background-removed image
                with open(bg_removed_path, 'wb') as f:
                    f.write(bg_removed_bytes)
                print(f"Background-removed image saved to {bg_removed_path}")
                timings.append(["Background Removal", f"{time.time() - step_start_time:.2f}"])
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
    print(f"Model: Stable Image Inpaint")
    print(f"Endpoint: {api_endpoint}")
    print(f"Input Image: {input_image_url}")
    print(f"Mask Image: {mask_image_url}")
    print(f"Prompt: {prompt}")
    print(f"Negative Prompt: {negative_prompt}")
    print(f"Grow Mask: {grow_mask}px")
    print(f"Seed: {seed}")
    print(f"Output Format: {output_format}")
    print(f"Style Preset: {style_preset or 'None'}")
    print(f"Remove Background: {remove_background}")
    print(f"Cost: 3 credits per generation")
    if remove_background:
        print(f"Background Removal Cost: 2 credits per generation")

if __name__ == "__main__":
    print("Running Stability AI Inpaint test...")
    try:
        test_image_to_image_mask()
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