import os
from supabase import create_client, Client


def get_supabase_client() -> Client:
    """Initializes and returns a Supabase client instance."""
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_SERVICE_KEY") # Use service key for backend operations
    if not url or not key:
        # In a real app, you'd handle this missing config more robustly
        print("Supabase URL or Service Key not found in environment variables.")
        raise ValueError("Supabase URL and Service Key must be set.")
    return create_client(url, key)


async def upload_image_to_storage(file_name: str, image_data: bytes, bucket_name: str = "concept_images") -> str:
    """
    Uploads image data to Supabase Storage and returns the public URL.

    Args:
        file_name: The desired name for the file in storage.
        image_data: The binary image data (e.g., from decoding base64).
        bucket_name: The target storage bucket.

    Returns:
        The public URL of the uploaded file.
    """
    supabase = get_supabase_client()
    # The upload method returns an object with data about the upload
    # The path should include the file name within the bucket
    try:
        response = supabase.storage.from_(bucket_name).upload(file_name, image_data)
        # Note: The structure of the response might vary slightly based on library version
        # and success, but the path is usually consistent for getting the URL.
        # We need the *public* URL, which is obtained via storage.from_(...).get_public_url(...)
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
        return public_url
    except Exception as e:
        print(f"Error uploading to Supabase Storage: {e}")
        # Handle specific Supabase storage errors if needed
        raise


async def create_concept_image_record(
    task_id: str,
    image_url: str,
    prompt: str | None = None,
    style: str | None = None,
):
    """
    Inserts a record for a generated concept image into the database.

    Args:
        task_id: The associated BFF task ID.
        image_url: The public URL of the image in Supabase Storage.
        prompt: The prompt used for generation.
        style: The style applied.
    """
    supabase = get_supabase_client()
    data = {
        "task_id": task_id,
        "image_url": image_url,
        "prompt": prompt,
        "style": style,
    }
    try:
        # The insert method returns an object with data about the insert result
        response = supabase.table("concept_images").insert([data]).execute()
        # Check for errors in the response object
        if response.data:
             print(f"Successfully inserted concept image record: {response.data}")
        elif response.error:
             print(f"Error inserting concept image record: {response.error}")
             raise Exception(f"Database insert error: {response.error.message}")

    except Exception as e:
        print(f"Error creating concept image record: {e}")
        raise 