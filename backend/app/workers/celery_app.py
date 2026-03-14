import os

from celery import Celery


celery_app = Celery(
    "sematrix",
    broker=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_default_queue="sematrix",
    timezone="UTC",
    beat_schedule={},
)
