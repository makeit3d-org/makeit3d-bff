import requests
import os
import time
from dotenv import load_dotenv
from io import BytesIO
import base64

def test_image_to_image():
    """
    Tests the Stability AI image-to-image functionality using the Structure endpoint.
    Downloads an input image, sends it to the API with a prompt and configuration,
    and saves the resulting image with execution timings.
    Optionally removes the background as a second API call.
    """
    load_dotenv()
    timings = []
    total_start_time = time.time()

    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        raise ValueError("STABILITY_API_KEY not found in environment variables. Make sure it's in your .env file.")

    # Configuration - modify these as needed
    api_endpoint = "https://api.stability.ai/v2beta/stable-image/control/style"
    
    # Input image URL (same as sketch-to-image test)
    input_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept"
    
    # Parameters (same as sketch-to-image test)
    prompt_text = "cat with blue body standing on its hind legs with front paws in the air, no background"
    negative_prompt = "blurry, low quality, distorted"
    style_preset = "3d-model"  # Options: 3d-model, analog-film, anime, cinematic, comic-book, digital-art, enhance, fantasy-art, isometric, line-art, low-poly, modeling-compound, neon-punk, origami, photographic, pixel-art, tile-texture
    output_format = "png"  # Options: png, jpeg, webp
    
    # Structure control parameters
    fidelity = 0.8  # How much influence the input image structure has (0.0 to 1.0)
    seed = 0  # 0 for random
    
    # Background removal option
    remove_background = False  # Set to True to remove background after generation
    
    output_dir = "tests/outputs"
    output_filename = f"stability_structure_image_to_image_output.{output_format}"
    output_path = os.path.join(output_dir, output_filename)
    
    # Background removal output path
    bg_removed_filename = f"stability_structure_image_to_image_no_bg.png"
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
    print(f"Sending request to Stability AI Structure endpoint: {api_endpoint}...")
    
    headers = {
        "authorization": f"Bearer {api_key}",
        "accept": "image/*",  # Request image bytes directly
    }
    
    files = {
        "image": ("input_image.jpg", BytesIO(input_image_bytes), "image/jpeg")
    }
    data = {
        "prompt": prompt_text,
        "fidelity": fidelity,
        "output_format": output_format,
        "seed": seed
    }
    if negative_prompt:
        data["negative_prompt"] = negative_prompt
    if style_preset:
        data["style_preset"] = style_preset

    try:
        response = requests.post(api_endpoint, headers=headers, files=files, data=data)
        timings.append(["API Call", f"{time.time() - step_start_time:.2f}"])
        
        if response.status_code == 200:
            print("Generation successful!")
            final_image_content = response.content
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
        
        bg_removal_endpoint = "https://api.stability.ai/v2beta/stable-image/edit/remove-background"
        bg_headers = {
            "authorization": f"Bearer {api_key}",
            "accept": "image/*",
        }
        
        bg_files = {
            "image": ("generated_image.png", BytesIO(final_image_content), "image/png")
        }
        bg_data = {
            "output_format": "png"
        }
        
        try:
            bg_response = requests.post(bg_removal_endpoint, headers=bg_headers, files=bg_files, data=bg_data)
            timings.append(["Remove Background", f"{time.time() - step_start_time:.2f}"])
            
            if bg_response.status_code == 200:
                print("Background removal successful!")
                bg_removed_content = bg_response.content
                
                # Save background-removed image
                step_start_time = time.time()
                print(f"Saving background-removed image to {bg_removed_path}...")
                try:
                    with open(bg_removed_path, 'wb') as f:
                        f.write(bg_removed_content)
                    print(f"Background-removed image saved successfully to {bg_removed_path}")
                    timings.append(["Save BG-Removed Image", f"{time.time() - step_start_time:.2f}"])
                except Exception as e:
                    timings.append(["Save BG-Removed Image", f"Failed: {e}"])
                    print(f"Failed to save background-removed image: {e}")
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
    print(f"Endpoint: Structure (image-to-image)")
    print(f"Prompt: {prompt_text}")
    print(f"Negative Prompt: {negative_prompt}")
    print(f"Style Preset: {style_preset}")
    print(f"Output Format: {output_format}")
    print(f"Fidelity: {fidelity}")
    print(f"Seed: {seed}")
    print(f"Remove Background: {remove_background}")

if __name__ == "__main__":
    print("Running Stability AI image-to-image test...")
    try:
        test_image_to_image()
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