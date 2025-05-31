import requests
import os
import time
from dotenv import load_dotenv
from io import BytesIO

def test_search_and_recolor():
    """
    Tests the Stability AI Search and Recolor functionality.
    Downloads the cat concept image, changes the cat from orange/tan with black stripes 
    to light blue with dark blue stripes, and saves the resulting image with execution timings.
    This API automatically segments the object and recolors it without requiring a mask.
    """
    load_dotenv()
    timings = []
    total_start_time = time.time()

    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        raise ValueError("STABILITY_API_KEY not found in environment variables. Make sure it's in your .env file.")

    # Configuration - modify these as needed
    api_endpoint = "https://api.stability.ai/v2beta/stable-image/edit/search-and-recolor"
    
    # Input image URL (sketch-cat-concept)
    input_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept"
    
    # Parameters for search and recolor
    prompt = "light blue cat with dark blue stripes, maintaining the same pose and expression"
    select_prompt = "cat"  # What to search for and recolor in the image
    negative_prompt = "blurry, low quality, distorted, orange, tan, brown, yellow"
    
    # Advanced parameters
    grow_mask = 3  # Default: 3, range: 0-20, grows mask edges for smoother transitions
    seed = 0  # 0 for random
    
    # Output settings
    output_format = "png"  # Options: png, jpeg, webp
    style_preset = None  # Optional: 3d-model, analog-film, anime, cinematic, comic-book, digital-art, enhance, fantasy-art, isometric, line-art, low-poly, modeling-compound, neon-punk, origami, photographic, pixel-art, tile-texture
    
    output_dir = "tests/outputs"
    output_filename = f"stability_search_recolor_output.{output_format}"
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
    print(f"Sending request to Stability AI Search and Recolor: {api_endpoint}...")
    
    headers = {
        "authorization": f"Bearer {api_key}",
        "accept": "image/*",  # Request image bytes directly
    }
    
    files = {
        "image": ("cat_concept.png", BytesIO(input_image_bytes), "image/png")
    }
    
    data = {
        "prompt": prompt,
        "select_prompt": select_prompt,
        "output_format": output_format,
        "grow_mask": grow_mask,
        "seed": seed
    }
    
    # Add optional parameters if specified
    if negative_prompt:
        data["negative_prompt"] = negative_prompt
    if style_preset:
        data["style_preset"] = style_preset

    # Debug output
    print(f"Request data: {data}")
    print(f"Headers: {headers}")
    print(f"Files: {list(files.keys())}")

    try:
        response = requests.post(api_endpoint, headers=headers, files=files, data=data)
        timings.append(["API Call", f"{time.time() - step_start_time:.2f}"])
        
        if response.status_code == 200:
            print("Recoloring successful!")
            final_image_content = response.content
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
        timings.append(["API Call", f"Failed: {error_message}"])
        raise Exception(error_message)
    except Exception as e:
        timings.append(["API Call", f"Failed: {e}"])
        raise Exception(f"Error during API call: {e}")

    # 3. Save image
    step_start_time = time.time()
    print(f"Saving recolored image to {output_path}...")
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
    print(f"Endpoint: Search and Recolor (synchronous)")
    print(f"Input Image: {input_image_url}")
    print(f"Prompt: {prompt}")
    print(f"Select Prompt: {select_prompt}")
    print(f"Negative Prompt: {negative_prompt}")
    print(f"Output Format: {output_format}")
    print(f"Grow Mask: {grow_mask}")
    print(f"Seed: {seed}")
    print(f"Style Preset: {style_preset or 'None'}")

if __name__ == "__main__":
    print("Running Stability AI Search and Recolor test...")
    print("Changing cat from orange/tan with black stripes to light blue with dark blue stripes...")
    try:
        test_search_and_recolor()
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