from supabase import create_client, Client
from app.config import settings
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
import httpx # For httpx.HTTPStatusError

supabase_client: Client = create_client(settings.supabase_url, settings.supabase_service_key)

async def fetch_asset_from_storage(asset_supabase_url: str) -> bytes:
    """Downloads an asset from a given Supabase Storage URL.

    Args:
        asset_supabase_url: The full public URL of the asset in Supabase Storage.

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
        # Standard prefix for public Supabase storage object URLs
        base_storage_path_prefix = "/storage/v1/object/public/"
        expected_prefix = normalized_supabase_url + base_storage_path_prefix

        if not asset_supabase_url.startswith(expected_prefix):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid Supabase Storage URL. Must start with '{expected_prefix}'."
            )

        bucket_and_path_str = asset_supabase_url.removeprefix(expected_prefix)
        
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
    asset_type_plural: str, # e.g., "concepts", "models"
    file_name: str, # e.g., "0.png", "model.glb"
    asset_data: bytes, 
    content_type: str
) -> str:
    """Uploads an asset to the configured Supabase Storage bucket.

    Args:
        task_id: The main task ID for namespacing.
        asset_type_plural: The type of asset (e.g., "concepts", "models"), used in the path.
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
    storage_path = f"{asset_type_plural}/{task_id}/{file_name}"
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
        # Construct the public URL.
        # Ensure no double slashes if supabase_url already has a trailing slash.
        normalized_supabase_url = settings.supabase_url.rstrip('/')
        public_url = f"{normalized_supabase_url}/storage/v1/object/public/{bucket_name}/{storage_path}"
        return public_url

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
        "task_id": task_id, # Ensuring task_id can also be updated if needed, though typically static for a record
        "status": status,
        "updated_at": "now()" 
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
        "status": status,
        "updated_at": "now()"
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

# Functions for Supabase interactions will be added here 