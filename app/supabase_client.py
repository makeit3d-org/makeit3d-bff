import os
from supabase import create_client, Client
import logging # Import logging

logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """Initializes and returns a Supabase client instance."""
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_SERVICE_KEY") # Use service key for backend operations
    if not url or not key:
        # In a real app, you'd handle this missing config more robustly
        logger.error("Supabase URL or Service Key not found in environment variables.")
        raise ValueError("Supabase URL and Service Key must be set.")
    return create_client(url, key)


async def upload_image_to_storage(file_name: str, image_data: bytes, bucket_name: str = "concept-images") -> str:
    """
    Uploads image data to Supabase Storage and returns the file path.

    Args:
        file_name: The desired name for the file in storage.
        image_data: The binary image data (e.g., from decoding base64).
        bucket_name: The target storage bucket.

    Returns:
        The file path within the bucket.
    """
    supabase = get_supabase_client()
    # The upload method returns an object with data about the upload
    # The path should include the file name within the bucket
    try:
        response = supabase.storage.from_(bucket_name).upload(file_name, image_data)
        # Note: The structure of the response might vary slightly based on library version
        # and success.

        # We return the file_name (which includes the path within the bucket)
        logger.info(f"Uploaded file {file_name} to bucket {bucket_name}.")
        return file_name
    except Exception as e:
        logger.error(f"Error uploading to Supabase Storage: {e}", exc_info=True)
        # Handle specific Supabase storage errors if needed
        raise


async def create_concept_image_record(
    task_id: str,
    image_url: str, # Now takes the image URL (BFF download URL)
    bucket_name: str = "concept-images", # Include bucket name in metadata
    prompt: str | None = None,
    style: str | None = None,
):
    """
    Inserts a record for a generated concept image into the database.

    Args:
        task_id: The associated BFF task ID.
        image_url: The URL (BFF download URL) for the image.
        bucket_name: The bucket name.
        prompt: The prompt used for generation.
        style: The style applied.
    """
    supabase = get_supabase_client()
    data = {
        "task_id": task_id,
        "image_url": image_url, # Store the image_url
        "bucket_name": bucket_name, # Store bucket_name
        "prompt": prompt,
        "style": style,
    }
    try:
        # The insert method returns an object with data about the insert result
        response = supabase.table("concept_images").insert([data]).execute()
        # Check for errors in the response object
        if response.data:
             logger.info(f"Successfully inserted concept image record: {response.data}")
        elif response.error:
             logger.error(f"Error inserting concept image record: {response.error}")
             raise Exception(f"Database insert error: {response.error.message}")

    except Exception as e:
        logger.error(f"Error creating concept image record: {e}", exc_info=True)
        raise


async def download_image_from_storage(file_path: str, bucket_name: str = "concept-images") -> bytes:
    """
    Downloads image data from Supabase Storage using the service key.

    Args:
        file_path: The file path within the bucket.
        bucket_name: The target storage bucket.

    Returns:
        The binary image data.
    """
    supabase = get_supabase_client()
    try:
        # The download method returns the file content directly
        response = supabase.storage.from_(bucket_name).download(file_path)
        logger.info(f"Downloaded file {file_path} from bucket {bucket_name}.")
        return response
    except Exception as e:
        logger.error(f"Error downloading from Supabase Storage: {e}", exc_info=True)
        # Handle specific Supabase storage errors if needed
        raise 