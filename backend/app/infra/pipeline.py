from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from celery import chord, group
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import Settings, get_logger, get_settings
from app.domain.pipeline import build_pipeline_stages
from app.infra.models import Note, PipelineRun
from app.workers.celery_app import celery_app


logger = get_logger(__name__)


@dataclass(frozen=True)
class PipelineRuntimeState:
    note_id: UUID
    index_version: int
    current_index_version: int
    pipeline_run_id: UUID
    snapshot_asset_ids: list[UUID]
    snapshot_link_ids: list[UUID]


class PipelineRuntimeRepository(Protocol):
    def get_runtime_state(self, *, note_id: UUID, index_version: int) -> PipelineRuntimeState | None: ...


class SqlAlchemyPipelineRuntimeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_runtime_state(self, *, note_id: UUID, index_version: int) -> PipelineRuntimeState | None:
        note = self._session.get(Note, note_id)
        if note is None:
            return None

        pipeline_run = self._session.scalar(
            select(PipelineRun).where(
                PipelineRun.note_id == note_id,
                PipelineRun.index_version == index_version,
            )
        )
        if pipeline_run is None:
            return None

        return PipelineRuntimeState(
            note_id=note_id,
            index_version=index_version,
            current_index_version=note.index_version,
            pipeline_run_id=pipeline_run.id,
            snapshot_asset_ids=list(pipeline_run.snapshot_asset_ids),
            snapshot_link_ids=list(pipeline_run.snapshot_link_ids),
        )


class CeleryPipelineDispatcher:
    def start_pipeline(self, *, note_id: UUID, index_version: int, request_id: str | None) -> None:
        celery_app.send_task(
            "sematrix.start_pipeline",
            kwargs={
                "note_id": str(note_id),
                "index_version": index_version,
                "request_id": request_id,
            },
        )


class CeleryPipelineOrchestrator:
    def __init__(
        self,
        *,
        runtime_repository: PipelineRuntimeRepository,
        settings: Settings,
        celery: Any,
        group_factory=group,
        chord_factory=chord,
    ) -> None:
        self._runtime_repository = runtime_repository
        self._settings = settings
        self._celery = celery
        self._group_factory = group_factory
        self._chord_factory = chord_factory

    def start_pipeline(
        self,
        *,
        note_id: UUID,
        index_version: int,
        request_id: str | None,
    ) -> dict[str, object]:
        runtime_state = self._runtime_repository.get_runtime_state(
            note_id=note_id,
            index_version=index_version,
        )
        if runtime_state is None:
            logger.info(
                "pipeline_orchestration_skipped",
                extra={
                    "event": "pipeline_orchestration_skipped",
                    "note_id": str(note_id),
                    "index_version": index_version,
                    "request_id": request_id,
                },
            )
            return {
                "status": "skipped",
                "dispatch": "missing_runtime_state",
                "note_id": str(note_id),
                "index_version": index_version,
                "stage_names": [],
            }

        if runtime_state.current_index_version != index_version:
            logger.info(
                "pipeline_orchestration_skipped",
                extra={
                    "event": "pipeline_orchestration_skipped",
                    "note_id": str(note_id),
                    "index_version": index_version,
                    "request_id": request_id,
                },
            )
            return {
                "status": "skipped",
                "dispatch": "stale_version",
                "note_id": str(note_id),
                "index_version": index_version,
                "stage_names": [],
            }

        stages = build_pipeline_stages(
            snapshot_asset_ids=runtime_state.snapshot_asset_ids,
            snapshot_link_ids=runtime_state.snapshot_link_ids,
            disable_link_fetch=self._settings.disable_link_fetch,
            disable_ocr=self._settings.disable_ocr,
            disable_image_caption=self._settings.disable_image_caption,
        )
        stage_names = [stage.name for stage in stages]

        finalize_kwargs = {
            "note_id": str(note_id),
            "index_version": index_version,
            "pipeline_run_id": str(runtime_state.pipeline_run_id),
            "request_id": request_id,
        }

        if not stages:
            self._celery.send_task(
                "sematrix.finalize_pipeline",
                kwargs={**finalize_kwargs, "stage_results": []},
            )
            return {
                "status": "scheduled",
                "dispatch": "direct_finalize",
                "note_id": str(note_id),
                "index_version": index_version,
                "stage_names": stage_names,
            }

        stage_signatures = [
            self._celery.signature(
                stage.task_name,
                kwargs={
                    "note_id": str(note_id),
                    "index_version": index_version,
                    "pipeline_run_id": str(runtime_state.pipeline_run_id),
                    "request_id": request_id,
                },
            )
            for stage in stages
        ]
        header = self._group_factory(stage_signatures)
        finalize_signature = self._celery.signature(
            "sematrix.finalize_pipeline",
            kwargs=finalize_kwargs,
        )
        finalize_signature.link_error(
            self._celery.signature(
                "sematrix.pipeline_failed",
                kwargs=finalize_kwargs,
            )
        )
        self._chord_factory(header)(finalize_signature)
        return {
            "status": "scheduled",
            "dispatch": "chord",
            "note_id": str(note_id),
            "index_version": index_version,
            "stage_names": stage_names,
        }


def build_pipeline_orchestrator(*, session: Session) -> CeleryPipelineOrchestrator:
    return CeleryPipelineOrchestrator(
        runtime_repository=SqlAlchemyPipelineRuntimeRepository(session=session),
        settings=get_settings(),
        celery=celery_app,
    )
