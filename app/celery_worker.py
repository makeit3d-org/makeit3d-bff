from celery import Celery
from app.config import settings

# Explicitly import task modules
# from app.tasks import generation_tasks # Removed to break circular import

# Configure Celery
celery_app = Celery(
    "makeit3d_bff",
    broker=settings.redis_url,
    backend=settings.redis_url
)

# Optional: Configure Celery to use UTC timezone
celery_app.conf.enable_utc = True
celery_app.conf.timezone = 'UTC'

# Configure task serialization to use JSON
celery_app.conf.task_serializer = 'json'
celery_app.conf.result_serializer = 'json'
celery_app.conf.accept_content = ['json']
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True

# Explicitly import task modules AFTER celery_app is defined
# This ensures tasks are registered with the 'celery_app' instance.
from app.tasks import generation_tasks

# autodiscover_tasks might now be redundant if tasks are explicitly imported this way,
# but can be left for robustness or if other task modules are added later without explicit imports.
celery_app.autodiscover_tasks(['app.tasks']) # Uncommented to ensure tasks are found 