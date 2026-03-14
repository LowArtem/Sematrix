from time import perf_counter
from uuid import UUID

from app.domain.system import WorkerHeartbeatService
from app.core import get_logger
from app.infra import SessionLocal
from app.infra.pipeline import build_pipeline_finalizer, build_pipeline_orchestrator, build_pipeline_stage_runner
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
    session = SessionLocal()
    try:
        orchestrator = build_pipeline_orchestrator(session=session)
        return orchestrator.start_pipeline(
            note_id=UUID(note_id),
            index_version=index_version,
            request_id=request_id,
        )
    finally:
        session.close()


@celery_app.task(bind=True, name="sematrix.process_links")
def process_links(
    self,
    note_id: str,
    index_version: int,
    pipeline_run_id: str,
    request_id: str | None = None,
) -> dict[str, object]:
    started_at = perf_counter()
    logger.info(
        "stage_requested",
        extra={
            "event": "stage_requested",
            "task_name": self.name,
            "note_id": note_id,
            "index_version": index_version,
            "request_id": request_id,
            "pipeline_run_id": pipeline_run_id,
        },
    )
    session = SessionLocal()
    try:
        stage_runner = build_pipeline_stage_runner(session=session)
        stage_result = stage_runner.process_links(
            note_id=UUID(note_id),
            index_version=index_version,
            pipeline_run_id=UUID(pipeline_run_id),
            request_id=request_id,
        )
    finally:
        session.close()

    return {
        **stage_result,
        "duration_ms": int((perf_counter() - started_at) * 1000),
    }


@celery_app.task(bind=True, name="sematrix.process_ocr")
def process_ocr(
    self,
    note_id: str,
    index_version: int,
    pipeline_run_id: str,
    request_id: str | None = None,
) -> dict[str, object]:
    started_at = perf_counter()
    logger.info(
        "stage_requested",
        extra={
            "event": "stage_requested",
            "task_name": self.name,
            "note_id": note_id,
            "index_version": index_version,
            "request_id": request_id,
            "pipeline_run_id": pipeline_run_id,
        },
    )
    session = SessionLocal()
    try:
        stage_runner = build_pipeline_stage_runner(session=session)
        stage_result = stage_runner.process_ocr(
            note_id=UUID(note_id),
            index_version=index_version,
            pipeline_run_id=UUID(pipeline_run_id),
            request_id=request_id,
        )
    finally:
        session.close()

    return {
        **stage_result,
        "duration_ms": int((perf_counter() - started_at) * 1000),
    }


@celery_app.task(bind=True, name="sematrix.process_image_caption")
def process_image_caption(
    self,
    note_id: str,
    index_version: int,
    pipeline_run_id: str,
    request_id: str | None = None,
) -> dict[str, object]:
    started_at = perf_counter()
    logger.info(
        "stage_requested",
        extra={
            "event": "stage_requested",
            "task_name": self.name,
            "note_id": note_id,
            "index_version": index_version,
            "request_id": request_id,
            "pipeline_run_id": pipeline_run_id,
        },
    )
    session = SessionLocal()
    try:
        stage_runner = build_pipeline_stage_runner(session=session)
        stage_result = stage_runner.process_image_caption(
            note_id=UUID(note_id),
            index_version=index_version,
            pipeline_run_id=UUID(pipeline_run_id),
            request_id=request_id,
        )
    finally:
        session.close()

    return {
        **stage_result,
        "duration_ms": int((perf_counter() - started_at) * 1000),
    }


@celery_app.task(bind=True, name="sematrix.finalize_pipeline")
def finalize_pipeline(
    self,
    stage_results: list[dict[str, object]],
    note_id: str,
    index_version: int,
    pipeline_run_id: str,
    request_id: str | None = None,
) -> dict[str, object]:
    logger.info(
        "pipeline_finalization_requested",
        extra={
            "event": "pipeline_finalization_requested",
            "task_name": self.name,
            "note_id": note_id,
            "index_version": index_version,
            "request_id": request_id,
            "pipeline_run_id": pipeline_run_id,
        },
    )
    session = SessionLocal()
    try:
        finalizer = build_pipeline_finalizer(session=session)
        return finalizer.finalize_pipeline(
            note_id=UUID(note_id),
            index_version=index_version,
            pipeline_run_id=UUID(pipeline_run_id),
            request_id=request_id,
            stage_results=stage_results,
        )
    finally:
        session.close()


@celery_app.task(bind=True, name="sematrix.pipeline_failed")
def pipeline_failed(
    self,
    *callback_args: object,
    note_id: str,
    index_version: int,
    pipeline_run_id: str,
    request_id: str | None = None,
    **callback_kwargs: object,
) -> dict[str, object]:
    logger.info(
        "pipeline_failure_requested",
        extra={
            "event": "pipeline_failure_requested",
            "task_name": self.name,
            "note_id": note_id,
            "index_version": index_version,
            "request_id": request_id,
            "pipeline_run_id": pipeline_run_id,
        },
    )
    return {
        "status": "accepted",
        "note_id": note_id,
        "index_version": index_version,
        "pipeline_run_id": pipeline_run_id,
        "callback_args": len(callback_args),
        "callback_kwargs": sorted(callback_kwargs),
    }
