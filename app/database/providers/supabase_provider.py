from typing import Optional, Dict, Any
from supabase import create_client, Client
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
import httpx
import logging

from ..base import DatabaseProvider, DatabaseConfig

logger = logging.getLogger(__name__)

class SupabaseProvider(DatabaseProvider):
    """Supabase implementation of DatabaseProvider"""
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self.client: Optional[Client] = None
        self.bucket_name = config.storage_config.get("bucket_name", "makeit3d-app-assets") if config.storage_config else "makeit3d-app-assets"
        self.images_table = config.credentials.get("images_table", "images")
        self.models_table = config.credentials.get("models_table", "models")
        self.credits_table = config.credentials.get("credits_table", "user_credits")
        self.transactions_table = config.credentials.get("transactions_table", "credit_transactions")
    
    async def connect(self) -> None:
        """Initialize Supabase client"""
        url = self.config.connection_url
        key = self.config.credentials.get("service_key")
        
        if not url or not key:
            raise ValueError("Supabase URL and Service Key must be provided")
        
        self.client = create_client(url, key)
        logger.info("Connected to Supabase")
    
    async def disconnect(self) -> None:
        """Close connection (Supabase doesn't require explicit disconnect)"""
        self.client = None
        logger.info("Disconnected from Supabase")
    
    def _get_client(self) -> Client:
        """Get Supabase client, ensuring it's connected"""
        if not self.client:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.client
    
    async def create_image_record(
        self,
        task_id: str,
        prompt: str,
        user_id: Optional[str] = None,
        style: Optional[str] = None,
        status: str = "pending",
        ai_service_task_id: Optional[str] = None,
        source_input_asset_id: Optional[str] = None,
        asset_url: str = "pending",
        is_public: bool = False,
        metadata: Optional[Dict] = None,
        image_type: str = "ai_generated"
    ) -> Dict[str, Any]:
        """Create a new image record in Supabase"""
        
        data = {
            "task_id": task_id,
            "prompt": prompt,
            "style": style,
            "status": status,
            "asset_url": asset_url,
            "is_public": is_public,
            "image_type": image_type,
            "metadata": metadata or {}
        }
        
        # Add optional fields if provided
        if user_id:
            data["user_id"] = user_id
        if ai_service_task_id:
            data["ai_service_task_id"] = ai_service_task_id
        if source_input_asset_id:
            data["source_input_asset_id"] = source_input_asset_id
        
        def _insert_sync():
            return self._get_client().table(self.images_table).insert([data]).execute()
        
        try:
            response = await run_in_threadpool(_insert_sync)
            if response.data:
                return response.data[0]
            else:
                raise HTTPException(status_code=500, detail="Failed to create image record")
        except Exception as e:
            logger.error(f"Error creating image record: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    async def update_image_record(
        self,
        task_id: str,
        image_id: str,
        status: str,
        asset_url: Optional[str] = None,
        ai_service_task_id: Optional[str] = None,
        prompt: Optional[str] = None,
        style: Optional[str] = None,
        source_input_asset_id: Optional[str] = None,
        is_public: Optional[bool] = None,
        metadata: Optional[Dict] = None,
        image_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing image record in Supabase"""
        
        update_data = {"status": status}
        
        # Add optional fields if provided
        if asset_url is not None:
            update_data["asset_url"] = asset_url
        if ai_service_task_id is not None:
            update_data["ai_service_task_id"] = ai_service_task_id
        if prompt is not None:
            update_data["prompt"] = prompt
        if style is not None:
            update_data["style"] = style
        if source_input_asset_id is not None:
            update_data["source_input_asset_id"] = source_input_asset_id
        if is_public is not None:
            update_data["is_public"] = is_public
        if metadata is not None:
            update_data["metadata"] = metadata
        if image_type is not None:
            update_data["image_type"] = image_type
        
        def _update_sync():
            return self._get_client().table(self.images_table).update(update_data).eq("id", image_id).execute()
        
        try:
            response = await run_in_threadpool(_update_sync)
            if response.data:
                return response.data[0]
            else:
                raise HTTPException(status_code=404, detail="Image record not found")
        except Exception as e:
            logger.error(f"Error updating image record: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    async def get_image_record_by_id(self, image_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an image record by ID from Supabase"""
        
        def _get_sync():
            return self._get_client().table(self.images_table).select("*").eq("id", image_id).execute()
        
        try:
            response = await run_in_threadpool(_get_sync)
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching image record: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    async def create_model_record(
        self,
        task_id: str,
        prompt: str,
        user_id: Optional[str] = None,
        style: Optional[str] = None,
        status: str = "pending",
        ai_service_task_id: Optional[str] = None,
        source_input_asset_id: Optional[str] = None,
        source_image_id: Optional[str] = None,
        asset_url: str = "pending",
        is_public: bool = False,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Create a new 3D model record in Supabase"""
        
        data = {
            "task_id": task_id,
            "prompt": prompt,
            "style": style,
            "status": status,
            "asset_url": asset_url,
            "is_public": is_public,
            "metadata": metadata or {}
        }
        
        # Add optional fields if provided
        if user_id:
            data["user_id"] = user_id
        if ai_service_task_id:
            data["ai_service_task_id"] = ai_service_task_id
        if source_input_asset_id:
            data["source_input_asset_id"] = source_input_asset_id
        if source_image_id:
            data["source_image_id"] = source_image_id
        
        def _insert_sync():
            return self._get_client().table(self.models_table).insert([data]).execute()
        
        try:
            response = await run_in_threadpool(_insert_sync)
            if response.data:
                return response.data[0]
            else:
                raise HTTPException(status_code=500, detail="Failed to create model record")
        except Exception as e:
            logger.error(f"Error creating model record: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    async def update_model_record(
        self,
        task_id: str,
        model_id: str,
        status: str,
        asset_url: Optional[str] = None,
        source_input_asset_id: Optional[str] = None,
        source_image_id: Optional[str] = None,
        ai_service_task_id: Optional[str] = None,
        prompt: Optional[str] = None,
        style: Optional[str] = None,
        is_public: Optional[bool] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Update an existing model record in Supabase"""
        
        update_data = {"status": status}
        
        # Add optional fields if provided
        if asset_url is not None:
            update_data["asset_url"] = asset_url
        if ai_service_task_id is not None:
            update_data["ai_service_task_id"] = ai_service_task_id
        if prompt is not None:
            update_data["prompt"] = prompt
        if style is not None:
            update_data["style"] = style
        if source_input_asset_id is not None:
            update_data["source_input_asset_id"] = source_input_asset_id
        if source_image_id is not None:
            update_data["source_image_id"] = source_image_id
        if is_public is not None:
            update_data["is_public"] = is_public
        if metadata is not None:
            update_data["metadata"] = metadata
        
        def _update_sync():
            return self._get_client().table(self.models_table).update(update_data).eq("id", model_id).execute()
        
        try:
            response = await run_in_threadpool(_update_sync)
            if response.data:
                return response.data[0]
            else:
                raise HTTPException(status_code=404, detail="Model record not found")
        except Exception as e:
            logger.error(f"Error updating model record: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    async def get_user_credits(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user credit information from Supabase"""
        
        def _get_sync():
            return self._get_client().table(self.credits_table).select("*").eq("user_id", user_id).execute()
        
        try:
            response = await run_in_threadpool(_get_sync)
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching user credits: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    async def check_and_deduct_credits(
        self, 
        user_id: str, 
        operation_key: str, 
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check and deduct credits for an operation in Supabase"""
        
        # This would need to implement the credit checking logic
        # For now, return a simplified response
        return {"success": True, "remaining_credits": 100}
    
    async def log_credit_transaction(
        self,
        user_id: str,
        transaction_type: str,
        credits_amount: int,
        operation_type: Optional[str] = None,
        operation_cost_usd: Optional[float] = None,
        task_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Log a credit transaction in Supabase"""
        
        data = {
            "user_id": user_id,
            "transaction_type": transaction_type,
            "credits_amount": credits_amount,
            "operation_type": operation_type,
            "operation_cost_usd": operation_cost_usd,
            "task_id": task_id,
            "description": description,
            "metadata": metadata or {}
        }
        
        def _insert_sync():
            return self._get_client().table(self.transactions_table).insert([data]).execute()
        
        try:
            response = await run_in_threadpool(_insert_sync)
            if response.data:
                return response.data[0]
            else:
                raise HTTPException(status_code=500, detail="Failed to log credit transaction")
        except Exception as e:
            logger.error(f"Error logging credit transaction: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    async def upload_asset(
        self,
        task_id: str,
        asset_type_plural: str,
        file_name: str,
        asset_data: bytes,
        content_type: str
    ) -> str:
        """Upload an asset to Supabase Storage and return the URL"""
        
        storage_path = f"{asset_type_plural}/{task_id}/{file_name}"
        
        def _upload_sync():
            return self._get_client().storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=asset_data,
                file_options={"content-type": content_type, "upsert": "true"}
            )
        
        try:
            await run_in_threadpool(_upload_sync)
            
            # Generate public URL
            public_url = f"{self.config.connection_url}/storage/v1/object/public/{self.bucket_name}/{storage_path}"
            return public_url
            
        except Exception as e:
            logger.error(f"Error uploading asset: {e}")
            raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
    
    async def fetch_asset(self, asset_url: str) -> bytes:
        """Fetch an asset from Supabase Storage"""
        
        try:
            # For public URLs, download via HTTP
            if "/storage/v1/object/public/" in asset_url:
                async with httpx.AsyncClient() as client:
                    response = await client.get(asset_url)
                    response.raise_for_status()
                    return response.content
            
            # For signed URLs or other cases, implement specific logic
            # This is a simplified implementation
            async with httpx.AsyncClient() as client:
                response = await client.get(asset_url)
                response.raise_for_status()
                return response.content
                
        except Exception as e:
            logger.error(f"Error fetching asset: {e}")
            raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}") 