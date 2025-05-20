from celery import Celery
from kombu import Queue # Import Queue
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
# Ensure task names in generation_tasks.py are precise for routing if using this method extensively.
# For MVP, we'll rely on explicit queue naming in apply_async or ensure task names are very distinct.
celery_app.conf.task_routes = {
    'app.tasks.generation_tasks.generate_tripo_refine_model_task': {'queue': 'tripo_refine_queue'},
    # Route other Tripo tasks to tripo_other_queue
    # A more generic router could be based on task name containing 'tripo' but not 'refine'
    'app.tasks.generation_tasks.generate_tripo_text_to_model_task': {'queue': 'tripo_other_queue'},
    'app.tasks.generation_tasks.generate_tripo_image_to_model_task': {'queue': 'tripo_other_queue'},
    'app.tasks.generation_tasks.generate_tripo_sketch_to_model_task': {'queue': 'tripo_other_queue'},
    'app.tasks.generation_tasks.generate_tripo_select_concept_task': {'queue': 'tripo_other_queue'},
    # OpenAI and other tasks will go to the 'default' queue by default
}

# Explicitly import task modules AFTER celery_app is defined
# This ensures tasks are registered with the 'celery_app' instance.
from app.tasks import generation_tasks

# autodiscover_tasks might now be redundant if tasks are explicitly imported this way,
# but can be left for robustness or if other task modules are added later without explicit imports.
celery_app.autodiscover_tasks(['app.tasks']) # Uncommented to ensure tasks are found 