from supabase import create_client, Client
from app.config import settings
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
import httpx # For httpx.HTTPStatusError
import logging

logger = logging.getLogger(__name__)

supabase_client: Client = create_client(settings.supabase_url, settings.supabase_service_key)

def get_asset_folder_path(asset_type_plural: str) -> str:
    """
    Get the correct folder path for asset storage based on test_assets_mode setting.
    
    This ONLY controls where files are stored in Supabase, not API behavior.
    
    Args:
        asset_type_plural: The base asset type (e.g., "concepts", "models", "input_assets")
                          or already processed path (e.g., "test_outputs/concepts")
    
    Returns:
        The full folder path to use for storage:
        - Test mode: "test_outputs/concepts", "test_outputs/models", "test_inputs/...", etc.
        - Production mode: "concepts", "models", "input_assets"
    """
    logger.info(f"get_asset_folder_path called with asset_type_plural='{asset_type_plural}', test_assets_mode={settings.test_assets_mode}")
    
    # Check if the path is already processed (contains test folders or slashes)
    if asset_type_plural.startswith("test_outputs/") or asset_type_plural.startswith("test_inputs/"):
        logger.info(f"get_asset_folder_path detected already processed test path: '{asset_type_plural}'")
        return asset_type_plural
    
    if settings.test_assets_mode:
        # In test mode, prefix with test_outputs for generated assets
        if asset_type_plural in ["concepts", "models"]:
            result = f"test_outputs/{asset_type_plural}"
            logger.info(f"get_asset_folder_path returning test path: '{result}'")
            return result
        # For input assets in tests, keep test_inputs structure  
        elif asset_type_plural.startswith("test_inputs"):
            logger.info(f"get_asset_folder_path returning test_inputs path: '{asset_type_plural}'")
            return asset_type_plural
        else:
            # Default test folder for other types
            result = f"test_outputs/{asset_type_plural}"
            logger.info(f"get_asset_folder_path returning default test path: '{result}'")
            return result
    else:
        # Production mode - return as-is
        logger.info(f"get_asset_folder_path returning production path: '{asset_type_plural}'")
        return asset_type_plural

def get_asset_type_for_concepts() -> str:
    """Get the correct asset type for concept images based on test mode."""
    return get_asset_folder_path("concepts")

def get_asset_type_for_models() -> str:
    """Get the correct asset type for 3D models based on test mode.""" 
    return get_asset_folder_path("models")

async def fetch_asset_from_storage(asset_supabase_url: str) -> bytes:
    """Downloads an asset from a given Supabase Storage URL.

    Args:
        asset_supabase_url: The full URL of the asset in Supabase Storage (public or signed).

    Returns:
        The asset content as bytes.

    Raises:
        HTTPException: 
            - 400 if the URL format is invalid.
            - 404 if the asset is not found.
            - 502 if there's an error communicating with Supabase Storage.
            - 500 for other unexpected errors.
    """
    try:
        normalized_supabase_url = settings.supabase_url.rstrip('/')
        
        # Check for both public and signed URL patterns
        public_prefix = normalized_supabase_url + "/storage/v1/object/public/"
        signed_prefix = normalized_supabase_url + "/storage/v1/object/sign/"
        
        is_public_url = asset_supabase_url.startswith(public_prefix)
        is_signed_url = asset_supabase_url.startswith(signed_prefix)
        
        if not (is_public_url or is_signed_url):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid Supabase Storage URL. Must start with '{public_prefix}' or '{signed_prefix}'."
            )

        # For signed URLs, download directly via HTTP (they already have authorization)
        if is_signed_url:
            async with httpx.AsyncClient() as client:
                response = await client.get(asset_supabase_url)
                response.raise_for_status()
                return response.content

        # For public URLs, extract bucket and path for authenticated download
        bucket_and_path_str = asset_supabase_url.removeprefix(public_prefix)
        
        if not bucket_and_path_str:
            raise HTTPException(status_code=400, detail="Bucket name and object path are missing in the URL.")

        path_parts = bucket_and_path_str.split('/', 1)
        bucket_name = path_parts[0]
        
        object_path = ""
        if len(path_parts) > 1:
            object_path = path_parts[1]

        if not bucket_name:
            # This case should ideally be caught by 'not bucket_and_path_str' earlier
            raise HTTPException(status_code=400, detail="Could not extract bucket name from URL.")
        
        if not object_path:
            # An object path is required to download a specific file.
            raise HTTPException(status_code=400, detail="Object path is missing in the URL.")

        # Define a sync wrapper for the Supabase call to run in a threadpool
        def _download_sync():
            return supabase_client.storage.from_(bucket_name).download(object_path)

        response_bytes = await run_in_threadpool(_download_sync)
        return response_bytes
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Asset not found at Supabase URL: {asset_supabase_url}")
        # Handle other HTTP errors from Supabase (e.g., 400 for bad path, 401/403 for RLS issues if not public)
        raise HTTPException(
            status_code=502, # Bad Gateway, as we failed to get a proper response from an upstream server
            detail=f"Failed to download asset from Supabase Storage. Upstream error: {e.response.status_code} - {e.response.text}"
        )
    except HTTPException: # Re-raise HTTPExceptions we've explicitly raised (like 400)
        raise
    except Exception as e:
        # Consider logging the error 'e' here for better debugging
        # logger.error(f"Unexpected error fetching from Supabase: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred while fetching asset from Supabase Storage: {str(e)}"
        )

async def upload_asset_to_storage(
    task_id: str, 
    asset_type_plural: str, # e.g., "concepts", "models" or already processed paths like "test_outputs/concepts"
    file_name: str, # e.g., "0.png", "model.glb"
    asset_data: bytes, 
    content_type: str
) -> str:
    """Uploads an asset to the configured Supabase Storage bucket.

    Args:
        task_id: The main task ID for namespacing.
        asset_type_plural: The type of asset (e.g., "concepts", "models"), used in the path.
                          Can be a simple type or already processed path.
        file_name: The name of the file.
        asset_data: The asset content as bytes.
        content_type: The MIME type of the asset.

    Returns:
        The full public URL of the uploaded asset in Supabase Storage.
    
    Raises:
        HTTPException: 
            - 502 if there's an error communicating with Supabase Storage during upload.
            - 500 for other unexpected errors.
    """
    storage_path = f"{get_asset_folder_path(asset_type_plural)}/{task_id}/{file_name}"
    bucket_name = settings.generated_assets_bucket_name

    try:
        # Define a sync wrapper for the Supabase call to run in a threadpool
        def _upload_sync():
            # The `upload` method returns an object that includes the `path` if successful,
            # or an error object. We check for the presence of an error.
            # Note: Supabase Python client might raise an exception for HTTP errors directly
            # depending on the version and underlying httpx behavior, which simplifies error checking.
            # For this implementation, we will rely on httpx.HTTPStatusError for HTTP errors.
            return supabase_client.storage.from_(bucket_name).upload(
                path=storage_path, 
                file=asset_data, 
                file_options={"content-type": content_type, "upsert": "true"} # upsert=true to overwrite if exists
            )

        await run_in_threadpool(_upload_sync)
        
        # If no exception was raised, the upload is considered successful.
        # Check if bucket is public to determine URL type
        def _check_bucket_public():
            buckets = supabase_client.storage.list_buckets()
            for bucket in buckets:
                if bucket.name == bucket_name:
                    return bucket.public
            return False  # Default to private if bucket not found
        
        is_bucket_public = await run_in_threadpool(_check_bucket_public)
        
        normalized_supabase_url = settings.supabase_url.rstrip('/')
        
        if is_bucket_public:
            # Construct the public URL for public buckets
            public_url = f"{normalized_supabase_url}/storage/v1/object/public/{bucket_name}/{storage_path}"
            return public_url
        else:
            # Create a signed URL for private buckets (expires in 1 hour by default)
            def _create_signed_url():
                response = supabase_client.storage.from_(bucket_name).create_signed_url(
                    path=storage_path, 
                    expires_in=3600  # 1 hour expiration
                )
                if isinstance(response, dict) and 'signedURL' in response:
                    return response['signedURL']
                elif isinstance(response, dict) and 'signed_url' in response:
                    return response['signed_url']
                else:
                    # Fallback: return the response itself if format is unexpected
                    return response
            
            signed_url = await run_in_threadpool(_create_signed_url)
            return signed_url

    except httpx.HTTPStatusError as e:
        # Handle HTTP errors from Supabase (e.g., 400 for bad path, 401/403 for RLS/permissions)
        raise HTTPException(
            status_code=502, # Bad Gateway, as we failed to get a proper response from an upstream server
            detail=f"Failed to upload asset to Supabase Storage. Upstream error: {e.response.status_code} - {e.response.text}"
        )
    except Exception as e:
        # Consider logging the error 'e' here
        # logger.error(f"Unexpected error uploading to Supabase: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred while uploading asset to Supabase Storage: {str(e)}"
        )

async def update_concept_image_record(
    task_id: str, 
    concept_image_id: str, # This is the specific ID of the concept image record itself
    status: str, 
    asset_url: str | None = None, # Made optional
    ai_service_task_id: str | None = None, 
    prompt: str | None = None, 
    style: str | None = None, 
    source_input_asset_id: str | None = None, 
    metadata: dict | None = None
) -> dict:
    """Updates a record in the concept_images table.

    Args:
        task_id: The main task ID.
        concept_image_id: The ID of the concept_image record to update.
        status: The new status of the concept image ('pending', 'processing', 'complete', 'failed').
        asset_url: Optional Supabase Storage URL of the generated concept image.
        ai_service_task_id: Optional ID from the AI service (e.g., OpenAI task ID).
        prompt: The prompt used for generation.
        style: The style used for generation.
        source_input_asset_id: The ID of the input_asset record used as source.
        metadata: Optional additional metadata.

    Returns:
        The updated record data from Supabase.

    Raises:
        HTTPException: 
            - 404 if the record is not found.
            - 502 if there's an error communicating with Supabase.
            - 500 for other unexpected errors.
    """
    table_name = settings.concept_images_table_name
    update_data = {
        "task_id": task_id,
        "status": status
    }
    if asset_url is not None: # Only add if provided
        update_data["asset_url"] = asset_url
    if ai_service_task_id is not None:
        update_data["ai_service_task_id"] = ai_service_task_id
    if prompt is not None: 
        update_data["prompt"] = prompt
    if style is not None: 
        update_data["style"] = style
    if source_input_asset_id is not None: 
        update_data["source_input_asset_id"] = source_input_asset_id
    if metadata is not None:
        update_data["metadata"] = metadata

    try:
        def _update_sync():
            response = (
                supabase_client.table(table_name)
                .update(update_data)
                .eq("id", concept_image_id)
                .execute()
            )
            if not response.data:
                raise HTTPException(status_code=404, detail=f"Concept image record with ID '{concept_image_id}' not found or not updated.")
            return response.data[0]

        updated_record = await run_in_threadpool(_update_sync)
        return updated_record

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to update concept image record in Supabase. Upstream error: {e.response.status_code} - {e.response.text}"
        )
    except HTTPException: # Re-raise HTTPExceptions from _update_sync
        raise
    except Exception as e:
        # logger.error(f"Unexpected error updating concept image in Supabase: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while updating concept image record: {str(e)}"
        )

async def update_model_record(
    task_id: str, 
    model_id: str, # This is the specific ID of the model record itself
    status: str, 
    asset_url: str | None = None, # Made optional
    source_input_asset_id: str | None = None, 
    source_concept_image_id: str | None = None, 
    ai_service_task_id: str | None = None, 
    prompt: str | None = None, 
    style: str | None = None, 
    metadata: dict | None = None
) -> dict:
    """Updates a record in the models table.

    Args:
        task_id: The main task ID.
        model_id: The ID of the model record to update.
        status: The new status of the model ('pending', 'processing', 'complete', 'failed').
        asset_url: Optional Supabase Storage URL of the generated model.
        source_input_asset_id: Optional ID of the input_asset record used directly.
        source_concept_image_id: Optional ID of the concept_image record used as source.
        ai_service_task_id: Optional ID from the AI service (e.g., Tripo task ID).
        prompt: The prompt used for generation.
        style: The style used for generation.
        metadata: Optional additional metadata.

    Returns:
        The updated record data from Supabase.

    Raises:
        HTTPException: 
            - 404 if the record is not found.
            - 502 if there's an error communicating with Supabase.
            - 500 for other unexpected errors.
    """
    table_name = settings.models_table_name
    update_data = {
        "task_id": task_id,
        "status": status
    }
    if asset_url is not None:
        update_data["asset_url"] = asset_url
    if source_input_asset_id is not None:
        update_data["source_input_asset_id"] = source_input_asset_id
    if source_concept_image_id is not None:
        update_data["source_concept_image_id"] = source_concept_image_id
    if ai_service_task_id is not None:
        update_data["ai_service_task_id"] = ai_service_task_id
    if prompt is not None:
        update_data["prompt"] = prompt
    if style is not None:
        update_data["style"] = style
    if metadata is not None:
        update_data["metadata"] = metadata

    try:
        def _update_sync():
            response = (
                supabase_client.table(table_name)
                .update(update_data)
                .eq("id", model_id)
                .execute()
            )
            if not response.data:
                raise HTTPException(status_code=404, detail=f"Model record with ID '{model_id}' not found or not updated.")
            return response.data[0]

        updated_record = await run_in_threadpool(_update_sync)
        return updated_record

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to update model record in Supabase. Upstream error: {e.response.status_code} - {e.response.text}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while updating model record: {str(e)}"
        )

async def create_concept_image_record(
    task_id: str,
    prompt: str,
    user_id: str | None = None,
    style: str | None = None,
    status: str = "pending", # Default initial status
    ai_service_task_id: str | None = None,
    source_input_asset_id: str | None = None,
    asset_url: str = "pending", # Placeholder value since this field is required in DB
    metadata: dict | None = None
) -> dict:
    """Creates a new record in the concept_images table.

    Args:
        task_id: The main task ID.
        prompt: The prompt used for generation.
        user_id: Optional ID of the user who initiated the task.
        style: Optional style used for generation.
        status: Initial status of the record (defaults to 'pending').
        ai_service_task_id: Optional ID from the AI service.
        source_input_asset_id: Optional ID of the input_asset record used as source.
        asset_url: Asset URL (defaults to "pending" placeholder since DB requires NOT NULL).
        metadata: Optional additional metadata.

    Returns:
        The newly created record data from Supabase, including its 'id'.

    Raises:
        HTTPException: 
            - 502 if there's an error communicating with Supabase.
            - 500 for other unexpected errors.
    """
    table_name = settings.concept_images_table_name
    insert_data = {
        "task_id": task_id,
        "prompt": prompt,
        "status": status,
        "asset_url": asset_url,  # Always include asset_url since it's required
    }
    if user_id is not None:
        insert_data["user_id"] = user_id
    if style is not None:
        insert_data["style"] = style
    if ai_service_task_id is not None:
        insert_data["ai_service_task_id"] = ai_service_task_id
    if source_input_asset_id is not None:
        insert_data["source_input_asset_id"] = source_input_asset_id
    if metadata is not None:
        insert_data["metadata"] = metadata

    try:
        def _insert_sync():
            response = (
                supabase_client.table(table_name)
                .insert(insert_data)
                .execute()
            )
            # Check if insert was successful and data is returned
            if not response.data:
                # This case might indicate an issue not caught by httpx.HTTPStatusError,
                # such as RLS preventing insert without returning a specific HTTP error code,
                # or a misconfiguration. For now, treat as a generic failure.
                raise HTTPException(status_code=502, detail="Failed to create concept image record in Supabase or no data returned.")
            return response.data[0] # Return the first (and should be only) created record

        created_record = await run_in_threadpool(_insert_sync)
        return created_record

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create concept image record in Supabase. Upstream error: {e.response.status_code} - {e.response.text}"
        )
    except HTTPException: # Re-raise HTTPExceptions from _insert_sync
        raise
    except Exception as e:
        # logger.error(f"Unexpected error creating concept image in Supabase: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while creating concept image record: {str(e)}"
        )

async def create_model_record(
    task_id: str,
    prompt: str, # Or derive from concept if source_concept_image_id is provided
    user_id: str | None = None,
    style: str | None = None, # Or derive from concept
    status: str = "pending", # Default initial status
    ai_service_task_id: str | None = None,
    source_input_asset_id: str | None = None, # If generating model directly from an input asset
    source_concept_image_id: str | None = None, # If generating model from a concept image
    asset_url: str = "pending", # Placeholder value since this field is required in DB
    metadata: dict | None = None
) -> dict:
    """Creates a new record in the models table.

    Args:
        task_id: The main task ID.
        prompt: The prompt used for generation.
        user_id: Optional ID of the user who initiated the task.
        style: Optional style used for generation.
        status: Initial status of the record (defaults to 'pending').
        ai_service_task_id: Optional ID from the AI service.
        source_input_asset_id: Optional ID of the input_asset used directly.
        source_concept_image_id: Optional ID of the concept_image record used as source.
        asset_url: Asset URL (defaults to "pending" placeholder since DB requires NOT NULL).
        metadata: Optional additional metadata.

    Returns:
        The newly created record data from Supabase, including its 'id'.

    Raises:
        HTTPException: 
            - 502 if there's an error communicating with Supabase.
            - 500 for other unexpected errors.
    """
    table_name = settings.models_table_name
    insert_data = {
        "task_id": task_id,
        "prompt": prompt,
        "status": status,
        "asset_url": asset_url,  # Always include asset_url since it's required
    }
    if user_id is not None:
        insert_data["user_id"] = user_id
    if style is not None:
        insert_data["style"] = style
    if ai_service_task_id is not None:
        insert_data["ai_service_task_id"] = ai_service_task_id
    if source_input_asset_id is not None:
        insert_data["source_input_asset_id"] = source_input_asset_id
    if source_concept_image_id is not None:
        insert_data["source_concept_image_id"] = source_concept_image_id
    if metadata is not None:
        insert_data["metadata"] = metadata

    try:
        def _insert_sync():
            response = (
                supabase_client.table(table_name)
                .insert(insert_data)
                .execute()
            )
            if not response.data:
                raise HTTPException(status_code=502, detail="Failed to create model record in Supabase or no data returned.")
            return response.data[0]

        created_record = await run_in_threadpool(_insert_sync)
        return created_record

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create model record in Supabase. Upstream error: {e.response.status_code} - {e.response.text}"
        )
    except HTTPException:
        raise
    except Exception as e:
        # logger.error(f"Unexpected error creating model in Supabase: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while creating model record: {str(e)}"
        )

async def get_concept_image_record_by_id(concept_image_id: str) -> dict | None:
    """Retrieves a concept image record from the concept_images table by its ID.

    Args:
        concept_image_id: The ID of the concept image record to retrieve.

    Returns:
        The concept image record data from Supabase, or None if not found.

    Raises:
        HTTPException: 
            - 502 if there's an error communicating with Supabase.
            - 500 for other unexpected errors.
    """
    table_name = settings.concept_images_table_name

    try:
        def _get_sync():
            response = (
                supabase_client.table(table_name)
                .select("*")
                .eq("id", concept_image_id)
                .execute()
            )
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        record = await run_in_threadpool(_get_sync)
        return record

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to retrieve concept image record from Supabase. Upstream error: {e.response.status_code} - {e.response.text}"
        )
    except Exception as e:
        # logger.error(f"Unexpected error retrieving concept image from Supabase: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while retrieving concept image record: {str(e)}"
        )

# Functions for Supabase interactions will be added here 