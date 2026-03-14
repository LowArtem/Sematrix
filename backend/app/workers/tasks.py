from app.domain.system import WorkerHeartbeatService
from app.workers.celery_app import celery_app


@celery_app.task(name="sematrix.ping")
def ping() -> str:
    service = WorkerHeartbeatService()
    return service.ping()
