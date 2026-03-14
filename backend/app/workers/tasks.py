from app.domain.system import WorkerHeartbeatService
from app.core import get_logger
from app.workers.celery_app import celery_app


logger = get_logger(__name__)


@celery_app.task(bind=True, name="sematrix.ping")
def ping(self) -> str:
    logger.info(
        "worker_heartbeat_requested",
        extra={"event": "worker_heartbeat_requested", "task_name": self.name},
    )
    service = WorkerHeartbeatService()
    return service.ping()
