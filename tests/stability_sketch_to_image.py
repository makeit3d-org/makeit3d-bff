import requests
import os
import time
from dotenv import load_dotenv
from io import BytesIO
import base64

def test_convert_sketch_to_image_async():
    """
    Tests the Stability AI sketch-to-image functionality, attempting asynchronous
    operation with polling, and measures execution time of each step.
    Downloads a sketch, sends it to the API with a prompt,
    polls for the result if asynchronous, and saves the resulting image.
    Optionally removes the background as a second API call.
    """
    load_dotenv()
    timings = []
    total_start_time = time.time()

    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        raise ValueError("STABILITY_API_KEY not found in environment variables. Make sure it's in your .env file.")

    sketch_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat2.png"
    prompt_text = "cute cartoon cat with stripes, crown and wings no background."
    control_strength = 0.4  # How much influence the sketch has (0.0 to 1.0)
    style_preset = "3d-model"  # Options: 3d-model, analog-film, anime, cinematic, comic-book, digital-art, enhance, fantasy-art, isometric, line-art, low-poly, modeling-compound, neon-punk, origami, photographic, pixel-art, tile-texture
    
    # Background removal option
    remove_background = False  # Set to True to remove background after generation
    
    output_dir = "tests/outputs"
    output_filename = "stability_sketch_cat_async_output.png"
    output_path = os.path.join(output_dir, output_filename)
    
    # Background removal output path
    bg_removed_filename = "stability_sketch_cat_async_no_bg.png"
    bg_removed_path = os.path.join(output_dir, bg_removed_filename)

    os.makedirs(output_dir, exist_ok=True)

    # 1. Download sketch
    step_start_time = time.time()
    print(f"Downloading sketch from {sketch_image_url}...")
    try:
        sketch_response = requests.get(sketch_image_url)
        sketch_response.raise_for_status()
        input_image_bytes = sketch_response.content
        image_content_for_upload = BytesIO(input_image_bytes)
        print("Sketch downloaded successfully.")
        timings.append(["Download Sketch", f"{time.time() - step_start_time:.2f}"])
    except requests.exceptions.RequestException as e:
        timings.append(["Download Sketch", f"Failed: {e}"])
        raise Exception(f"Failed to download sketch image: {e}")

    # 2. Initial API Request (attempt async)
    step_start_time = time.time()
    api_endpoint_sketch = "https://api.stability.ai/v2beta/stable-image/control/sketch"
    print(f"Sending initial request to Stability AI: {api_endpoint_sketch}...")
    
    headers = {
        "authorization": f"Bearer {api_key}",
        "accept": "application/json", # Request JSON response to get generation_id for async
    }
    
    files = {
        "image": ("sketch_cat.jpg", image_content_for_upload, "image/jpeg")
    }
    
    data = {
        "prompt": prompt_text,
        "output_format": "png",
        "control_strength": control_strength,
        "style_preset": style_preset
    }

    generation_id = None
    final_image_content = None

    try:
        response = requests.post(api_endpoint_sketch, headers=headers, files=files, data=data)
        timings.append(["Initial API Call", f"{time.time() - step_start_time:.2f}"])
        response_json = response.json()

        if response.status_code == 202: # Accepted for asynchronous processing
            generation_id = response_json.get("id")
            if not generation_id:
                raise Exception(f"API returned 202 but no generation ID. Response: {response_json}")
            print(f"Async generation started. Generation ID: {generation_id}")
        elif response.status_code == 200: # Synchronous completion (image in response)
            print("API returned 200 (synchronous). Processing image data.")
            # Expecting image data, potentially base64 encoded if not directly binary due to accept header
            # This part might need adjustment based on actual API behavior with accept: application/json
            if "image" in response_json: # Assuming 'image' key holds base64 data
                 final_image_content = base64.b64decode(response_json["image"])
            elif response.headers.get('content-type', '').startswith('image/'):
                 # This case is less likely with accept: application/json but good to check
                 final_image_content = response.content
            else:
                 raise Exception(f"API returned 200 with JSON, but no clear image data. Response: {response_json}")
        else:
            response.raise_for_status() # Will raise HTTPError for other bad statuses

    except requests.exceptions.HTTPError as e:
        error_message = f"API Error during initial call: {e.response.status_code}"
        try:
            error_details = e.response.json()
            error_message += f" - {error_details}"
        except requests.exceptions.JSONDecodeError:
            error_message += f" - {e.response.text}"
        timings.append(["Initial API Call", f"Failed: {error_message}"])
        raise Exception(error_message)
    except Exception as e:
        timings.append(["Initial API Call", f"Failed: {e}"])
        raise Exception(f"Error during initial API call: {e}")

    # 3. Polling for result (if async)
    if generation_id:
        step_start_time = time.time()
        api_endpoint_result = f"https://api.stability.ai/v2beta/results/{generation_id}"
        print(f"Polling for results at: {api_endpoint_result}")
        polling_attempts = 0
        max_polling_attempts = 60 # Approx 10 minutes if polling every 10s
        poll_interval = 1 # seconds

        while polling_attempts < max_polling_attempts:
            polling_attempts += 1
            print(f"Polling attempt {polling_attempts}...")
            try:
                poll_response = requests.get(
                    api_endpoint_result,
                    headers={
                        'accept': "image/png", # Request final image as png bytes
                        'authorization': f"Bearer {api_key}"
                    }
                )

                if poll_response.status_code == 202: # In progress
                    print("Generation in-progress, waiting...")
                    time.sleep(poll_interval)
                elif poll_response.status_code == 200: # Complete
                    print("Generation complete!")
                    final_image_content = poll_response.content
                    timings.append([f"Polling ({polling_attempts} attempts)", f"{time.time() - step_start_time:.2f}"])
                    break 
                else:
                    poll_response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                error_message = f"API Error during polling: {e.response.status_code}"
                try: error_details = e.response.json(); error_message += f" - {error_details}"
                except: error_message += f" - {e.response.text}"
                timings.append([f"Polling ({polling_attempts} attempts)", f"Failed: {error_message}"])
                raise Exception(error_message)
            except Exception as e:
                timings.append([f"Polling ({polling_attempts} attempts)", f"Failed: {e}"])
                raise Exception(f"Error during polling: {e}")
        else: # Max attempts reached
            timings.append([f"Polling ({polling_attempts} attempts)", "Failed: Max attempts reached"])
            raise Exception("Max polling attempts reached. Generation did not complete in time.")

    # 4. Save image
    if final_image_content:
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
    else:
        timings.append(["Save Image", "Skipped: No image content to save"])
        print("No final image content was retrieved to save.")

    # 5. Remove background (optional)
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
    print(f"Endpoint: Sketch Control (sketch-to-image)")
    print(f"Prompt: {prompt_text}")
    print(f"Control Strength: {control_strength}")
    print(f"Style Preset: {style_preset}")
    print(f"Remove Background: {remove_background}")

if __name__ == "__main__":
    print("Running Stability AI sketch-to-image test (async attempt)...")
    try:
        test_convert_sketch_to_image_async()
        print("\nTest completed.")
    except Exception as e:
        print(f"\nTest failed: {e}")
        # If timings were partially collected before failure, print them
        if 'timings' in locals() and timings:
             print("\n--- Partial Execution Timings ---")
             print(f"{'Step':<40} {'Duration (s)':<15}")
             print("-" * 55)
             for step, duration in timings:
                 print(f"{step:<40} {duration:<15}") 