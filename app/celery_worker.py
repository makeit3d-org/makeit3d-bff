from celery import Celery
from kombu import Queue # Import Queue
from config import settings

# Explicitly import task modules
# from app.tasks import generation_tasks # Removed to break circular import (split into separate files)

# Configure Celery
celery_app = Celery(
    "makeit3d_bff",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Optional: Configure Celery to use UTC timezone
celery_app.conf.enable_utc = True
celery_app.conf.timezone = 'UTC'

# Configure task serialization to use JSON (secure)
celery_app.conf.task_serializer = 'json'
celery_app.conf.result_serializer = 'json'
celery_app.conf.accept_content = ['json']
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True

# Define task queues
celery_app.conf.task_queues = (
    Queue('default',    routing_key='task.default'),
    Queue('tripo_other_queue', routing_key='task.tripo_other'),
    Queue('tripo_refine_queue', routing_key='task.tripo_refine'),
)
celery_app.conf.task_default_queue = 'default'
celery_app.conf.task_default_exchange = 'default'
celery_app.conf.task_default_routing_key = 'task.default'

# Route tasks to specific queues
# Send image-related tasks (OpenAI, Stability, Recraft, Flux) to default queue since celery_worker_default handles them
# Send model tasks (Tripo, Stability 3D) to their respective specialized queues
celery_app.conf.task_routes = {
    'tasks.generation_image_tasks.generate_openai_image_task': {'queue': 'default'},
    'tasks.generation_image_tasks.generate_stability_image_task': {'queue': 'default'},
    'tasks.generation_image_tasks.generate_recraft_image_task': {'queue': 'default'},
    'tasks.generation_image_tasks.generate_flux_image_task': {'queue': 'default'},
    'tasks.generation_model_tasks.generate_stability_model_task': {'queue': 'default'},
    'tasks.generation_model_tasks.generate_tripo_text_to_model_task': {'queue': 'tripo_other_queue'},
    'tasks.generation_model_tasks.generate_tripo_image_to_model_task': {'queue': 'tripo_other_queue'},
    'tasks.generation_model_tasks.generate_tripo_refine_model_task': {'queue': 'tripo_refine_queue'},
    # Any other tasks will go to the 'default' queue by default
}

# Explicitly import task modules AFTER celery_app is defined
# This ensures tasks are registered with the 'celery_app' instance.
from tasks import generation_image_tasks, generation_model_tasks

# autodiscover_tasks might now be redundant if tasks are explicitly imported this way,
# but can be left for robustness or if other task modules are added later without explicit imports.
celery_app.autodiscover_tasks(['tasks']) # Discover tasks from the tasks module 