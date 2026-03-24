from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "uradisam_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=['app.workers.tasks'],
    task_acks_late=True,
    task_track_started=True
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    worker_prefetch_multiplier=1,
    task_acks_late=True
)