from celery import Celery
from app.config import settings

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

# Auto-discover tasks in the 'tasks' module (we will create this next)
# celery_app.autodiscover_tasks(['app.tasks']) 