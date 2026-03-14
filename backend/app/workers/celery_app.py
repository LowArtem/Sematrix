from celery import Celery

from app.core import get_settings


settings = get_settings()


celery_app = Celery(
    "sematrix",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_default_queue="sematrix",
    timezone="UTC",
    beat_schedule={},
)
