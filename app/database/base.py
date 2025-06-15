from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    """Database configuration for different providers"""
    provider: str  # 'supabase', 'postgres', 'mongodb', etc.
    connection_url: str
    credentials: Dict[str, Any]
    storage_config: Optional[Dict[str, Any]] = None

class DatabaseProvider(ABC):
    """Abstract base class for all database providers"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
    
    @abstractmethod
    async def connect(self) -> None:
        """Initialize database connection"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close database connection"""
        pass
    
    # Image Operations
    @abstractmethod
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
        """Create a new image record"""
        pass
    
    @abstractmethod
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
        """Update an existing image record"""
        pass
    
    @abstractmethod
    async def get_image_record_by_id(self, image_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an image record by ID"""
        pass
    
    # Model Operations
    @abstractmethod
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
        """Create a new 3D model record"""
        pass
    
    @abstractmethod
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
        """Update an existing model record"""
        pass
    
    # Credit Operations
    @abstractmethod
    async def get_user_credits(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user credit information"""
        pass
    
    @abstractmethod
    async def check_and_deduct_credits(
        self, 
        user_id: str, 
        operation_key: str, 
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check and deduct credits for an operation"""
        pass
    
    @abstractmethod
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
        """Log a credit transaction"""
        pass
    
    # Storage Operations
    @abstractmethod
    async def upload_asset(
        self,
        task_id: str,
        asset_type_plural: str,
        file_name: str,
        asset_data: bytes,
        content_type: str
    ) -> str:
        """Upload an asset and return the URL"""
        pass
    
    @abstractmethod
    async def fetch_asset(self, asset_url: str) -> bytes:
        """Fetch an asset from storage"""
        pass 