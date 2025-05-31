import requests
import os
import time
from dotenv import load_dotenv
from io import BytesIO

def test_image_to_model():
    """
    Tests the Stability AI Stable Point Aware 3D (SPAR3D) functionality.
    Downloads an input image, sends it to the API to generate a 3D model,
    and saves the resulting GLB file with execution timings.
    
    Features:
    - Real-time 3D object creation from single image
    - Point-cloud diffusion + mesh regression
    - Improved backside prediction
    - 4 credits per generation
    """
    load_dotenv()
    timings = []
    total_start_time = time.time()

    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        raise ValueError("STABILITY_API_KEY not found in environment variables. Make sure it's in your .env file.")

    # Configuration - modify these as needed
    api_endpoint = "https://api.stability.ai/v2beta/3d/stable-point-aware-3d"
    
    # Input image URL (sketch-cat-concept from Supabase)
    #input_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//sketch-cat-concept"
    input_image_url = "https://iadsbhyztbokarclnzzk.supabase.co/storage/v1/object/public/makeit3d-public//model_man.png"
    
    # Parameters
    texture_resolution = 2048  # Options: 512, 1024, 2048 (higher = more detail, larger file)
    remesh = None  # Options: None, "quad", "triangle" (None = no remeshing, quad = for DCC tools)
    foreground_ratio = 1.3  # Range: 1.0-2.0 (controls padding around object)
    target_type = "none"  # Options: "none", "vertex", "face"
    target_count = 10000  # Range: 100-20000 (vertex/face count if target_type is set)
    guidance_scale = 6  # Range: 1-10 (point diffusion guidance, 3 is optimal)
    seed = 0  # 0 for random
    
    output_dir = "tests/outputs"
    output_filename = "stability_spar3d_cat_model.glb"
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
    print(f"Sending request to Stability AI SPAR3D: {api_endpoint}...")
    
    headers = {
        "authorization": f"Bearer {api_key}",
        # content-type will be automatically set by requests for multipart/form-data
    }
    
    files = {
        "image": ("sketch_cat_concept.png", BytesIO(input_image_bytes), "image/png")
    }
    
    data = {
        "texture_resolution": str(texture_resolution),
        "foreground_ratio": str(foreground_ratio),
        "target_type": target_type,
        "target_count": str(target_count),
        "guidance_scale": str(guidance_scale),
        "seed": str(seed)
    }
    
    # Add remesh parameter only if it's not None
    if remesh is not None:
        data["remesh"] = remesh

    try:
        response = requests.post(api_endpoint, headers=headers, files=files, data=data)
        timings.append(["API Call", f"{time.time() - step_start_time:.2f}"])
        
        if response.status_code == 200:
            print("3D model generation successful!")
            model_content = response.content
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

    # 3. Save 3D model
    step_start_time = time.time()
    print(f"Saving 3D model to {output_path}...")
    try:
        with open(output_path, 'wb') as f:
            f.write(model_content)
        
        # Get file size for reporting
        file_size_mb = len(model_content) / (1024 * 1024)
        print(f"3D model saved successfully to {output_path}")
        print(f"Model file size: {file_size_mb:.2f} MB")
        timings.append(["Save 3D Model", f"{time.time() - step_start_time:.2f}"])
    except Exception as e:
        timings.append(["Save 3D Model", f"Failed: {e}"])
        raise Exception(f"Failed to save 3D model: {e}")

    total_duration = time.time() - total_start_time
    timings.append(["Total Execution Time", f"{total_duration:.2f}"])
    
    print("\n--- Execution Timings ---")
    print(f"{'Step':<40} {'Duration (s)':<15}")
    print("-" * 55)
    for step, duration in timings:
        print(f"{step:<40} {duration:<15}")
    
    print(f"\n--- Configuration Used ---")
    print(f"Model: Stable Point Aware 3D (SPAR3D)")
    print(f"Endpoint: {api_endpoint}")
    print(f"Input Image: {input_image_url}")
    print(f"Texture Resolution: {texture_resolution}px")
    print(f"Remesh: {remesh or 'None'}")
    print(f"Foreground Ratio: {foreground_ratio}")
    print(f"Target Type: {target_type}")
    print(f"Target Count: {target_count}")
    print(f"Guidance Scale: {guidance_scale}")
    print(f"Seed: {seed}")
    print(f"Output Format: GLB (glTF Binary)")
    print(f"Cost: 4 credits per generation")

if __name__ == "__main__":
    print("Running Stability AI Stable Point Aware 3D (SPAR3D) test...")
    try:
        test_image_to_model()
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