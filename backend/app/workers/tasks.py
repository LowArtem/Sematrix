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


@celery_app.task(bind=True, name="sematrix.start_pipeline")
def start_pipeline(
    self,
    note_id: str,
    index_version: int,
    request_id: str | None = None,
) -> dict[str, object]:
    logger.info(
        "pipeline_entrypoint_requested",
        extra={
            "event": "pipeline_entrypoint_requested",
            "task_name": self.name,
            "note_id": note_id,
            "index_version": index_version,
            "request_id": request_id,
        },
    )
    return {
        "status": "accepted",
        "note_id": note_id,
        "index_version": index_version,
    }
