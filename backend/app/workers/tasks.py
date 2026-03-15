from time import perf_counter
from uuid import UUID

from app.core import get_logger, get_settings
from app.domain.notes import DraftCleanupService
from app.domain.system import WorkerHeartbeatService
from app.infra import SessionLocal
from app.infra.notes import SqlAlchemyNoteRepository
from app.infra.pipeline import (
    build_pipeline_failure_handler,
    build_pipeline_finalizer,
    build_pipeline_orchestrator,
    build_pipeline_stage_runner,
)
from app.workers.celery_app import celery_app


logger = get_logger(__name__)
settings = get_settings()

NETWORK_TASK_AUTORETRY_FOR = (Exception,)
NETWORK_TASK_RETRY_KWARGS = {"max_retries": 2}
NETWORK_TASK_RETRY_BACKOFF = True
NETWORK_TASK_RETRY_JITTER = False

ENRICHMENT_TASK_AUTORETRY_FOR = (Exception,)
ENRICHMENT_TASK_RETRY_KWARGS = {"max_retries": 1}


@celery_app.task(bind=True, name="sematrix.ping")
def ping(self) -> str:
    logger.info(
        "worker_heartbeat_requested",
        extra={"event": "worker_heartbeat_requested", "task_name": self.name},
    )
    service = WorkerHeartbeatService()
    return service.ping()


@celery_app.task(bind=True, name="sematrix.cleanup_drafts")
def cleanup_drafts(self) -> dict[str, object]:
    logger.info(
        "draft_cleanup_requested",
        extra={
            "event": "draft_cleanup_requested",
            "task_name": self.name,
        },
    )
    session = SessionLocal()
    try:
        service = DraftCleanupService(note_repository=SqlAlchemyNoteRepository(session=session))
        result = service.cleanup_expired_empty_drafts(ttl_hours=settings.draft_ttl_hours)
    finally:
        session.close()

    logger.info(
        "draft_cleanup_finished",
        extra={
            "event": "draft_cleanup_finished",
            "task_name": self.name,
            "candidate_count": result.candidate_count,
            "deleted_draft_count": result.deleted_draft_count,
            "deleted_asset_count": result.deleted_asset_count,
            "deletion_errors": result.deletion_errors,
        },
    )
    return {
        "candidate_count": result.candidate_count,
        "deleted_draft_count": result.deleted_draft_count,
        "deleted_asset_count": result.deleted_asset_count,
        "deletion_errors": result.deletion_errors,
    }


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


@celery_app.task(
    bind=True,
    name="sematrix.process_links",
    autoretry_for=NETWORK_TASK_AUTORETRY_FOR,
    retry_kwargs=NETWORK_TASK_RETRY_KWARGS,
    retry_backoff=NETWORK_TASK_RETRY_BACKOFF,
    retry_jitter=NETWORK_TASK_RETRY_JITTER,
)
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


@celery_app.task(
    bind=True,
    name="sematrix.process_ocr",
    autoretry_for=ENRICHMENT_TASK_AUTORETRY_FOR,
    retry_kwargs=ENRICHMENT_TASK_RETRY_KWARGS,
)
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


@celery_app.task(
    bind=True,
    name="sematrix.process_image_caption",
    autoretry_for=ENRICHMENT_TASK_AUTORETRY_FOR,
    retry_kwargs=ENRICHMENT_TASK_RETRY_KWARGS,
)
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
        try:
            return build_pipeline_finalizer(session=session).finalize_pipeline(
                note_id=UUID(note_id),
                index_version=index_version,
                pipeline_run_id=UUID(pipeline_run_id),
                request_id=request_id,
                stage_results=stage_results,
            )
        except Exception as exc:
            session.rollback()
            return build_pipeline_failure_handler(session=session).handle_failure(
                note_id=UUID(note_id),
                index_version=index_version,
                pipeline_run_id=UUID(pipeline_run_id),
                request_id=request_id,
                callback_args=(),
                callback_kwargs={
                    "failed_task_name": self.name,
                    "processing_error": str(exc),
                },
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
    session = SessionLocal()
    try:
        return build_pipeline_failure_handler(session=session).handle_failure(
            note_id=UUID(note_id),
            index_version=index_version,
            pipeline_run_id=UUID(pipeline_run_id),
            request_id=request_id,
            callback_args=callback_args,
            callback_kwargs=callback_kwargs,
        )
    finally:
        session.close()
