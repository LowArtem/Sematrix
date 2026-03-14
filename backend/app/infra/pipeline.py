from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol
from uuid import UUID

from celery import chord, group
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import Settings, get_logger, get_settings
from app.domain.pipeline import build_pipeline_stages, compute_snapshot_hash
from app.infra.models import Note, NoteAsset, NoteLink, PipelineRun
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


@dataclass(frozen=True)
class PipelineStageRuntimeState:
    note_id: UUID
    index_version: int
    current_index_version: int
    pipeline_run_id: UUID
    pipeline_run_note_id: UUID
    pipeline_run_index_version: int
    snapshot_asset_ids: list[UUID]
    snapshot_link_ids: list[UUID]
    snapshot_hash: str


class PipelineRuntimeRepository(Protocol):
    def get_runtime_state(self, *, note_id: UUID, index_version: int) -> PipelineRuntimeState | None: ...

    def get_stage_runtime_state(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
    ) -> PipelineStageRuntimeState | None: ...

    def list_snapshot_asset_ids(self, *, note_id: UUID, snapshot_asset_ids: list[UUID]) -> list[UUID]: ...

    def list_snapshot_link_ids(self, *, note_id: UUID, snapshot_link_ids: list[UUID]) -> list[UUID]: ...


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

    def get_stage_runtime_state(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
    ) -> PipelineStageRuntimeState | None:
        note = self._session.get(Note, note_id)
        if note is None:
            return None

        pipeline_run = self._session.get(PipelineRun, pipeline_run_id)
        if pipeline_run is None:
            return None

        return PipelineStageRuntimeState(
            note_id=note_id,
            index_version=index_version,
            current_index_version=note.index_version,
            pipeline_run_id=pipeline_run.id,
            pipeline_run_note_id=pipeline_run.note_id,
            pipeline_run_index_version=pipeline_run.index_version,
            snapshot_asset_ids=list(pipeline_run.snapshot_asset_ids),
            snapshot_link_ids=list(pipeline_run.snapshot_link_ids),
            snapshot_hash=pipeline_run.snapshot_hash,
        )

    def list_snapshot_asset_ids(self, *, note_id: UUID, snapshot_asset_ids: list[UUID]) -> list[UUID]:
        if not snapshot_asset_ids:
            return []

        existing_asset_ids = set(
            self._session.scalars(
                select(NoteAsset.asset_id).where(
                    NoteAsset.note_id == note_id,
                    NoteAsset.asset_id.in_(snapshot_asset_ids),
                )
            )
        )
        return [asset_id for asset_id in snapshot_asset_ids if asset_id in existing_asset_ids]

    def list_snapshot_link_ids(self, *, note_id: UUID, snapshot_link_ids: list[UUID]) -> list[UUID]:
        if not snapshot_link_ids:
            return []

        existing_link_ids = set(
            self._session.scalars(
                select(NoteLink.id).where(
                    NoteLink.note_id == note_id,
                    NoteLink.id.in_(snapshot_link_ids),
                )
            )
        )
        return [link_id for link_id in snapshot_link_ids if link_id in existing_link_ids]


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


class PipelineStageRunner:
    def __init__(self, *, runtime_repository: PipelineRuntimeRepository) -> None:
        self._runtime_repository = runtime_repository

    def process_links(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
        request_id: str | None,
    ) -> dict[str, object]:
        return self._run_stage(
            stage_name="process_links",
            note_id=note_id,
            index_version=index_version,
            pipeline_run_id=pipeline_run_id,
            request_id=request_id,
            snapshot_target_ids_getter=lambda state: state.snapshot_link_ids,
            existing_target_ids_loader=lambda snapshot_target_ids: self._runtime_repository.list_snapshot_link_ids(
                note_id=note_id,
                snapshot_link_ids=snapshot_target_ids,
            ),
        )

    def process_ocr(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
        request_id: str | None,
    ) -> dict[str, object]:
        return self._run_stage(
            stage_name="process_ocr",
            note_id=note_id,
            index_version=index_version,
            pipeline_run_id=pipeline_run_id,
            request_id=request_id,
            snapshot_target_ids_getter=lambda state: state.snapshot_asset_ids,
            existing_target_ids_loader=lambda snapshot_target_ids: self._runtime_repository.list_snapshot_asset_ids(
                note_id=note_id,
                snapshot_asset_ids=snapshot_target_ids,
            ),
        )

    def process_image_caption(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
        request_id: str | None,
    ) -> dict[str, object]:
        return self._run_stage(
            stage_name="process_image_caption",
            note_id=note_id,
            index_version=index_version,
            pipeline_run_id=pipeline_run_id,
            request_id=request_id,
            snapshot_target_ids_getter=lambda state: state.snapshot_asset_ids,
            existing_target_ids_loader=lambda snapshot_target_ids: self._runtime_repository.list_snapshot_asset_ids(
                note_id=note_id,
                snapshot_asset_ids=snapshot_target_ids,
            ),
        )

    def _run_stage(
        self,
        *,
        stage_name: str,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
        request_id: str | None,
        snapshot_target_ids_getter: Callable[[PipelineStageRuntimeState], list[UUID]],
        existing_target_ids_loader: Callable[[list[UUID]], list[UUID]],
    ) -> dict[str, object]:
        runtime_state = self._runtime_repository.get_stage_runtime_state(
            note_id=note_id,
            index_version=index_version,
            pipeline_run_id=pipeline_run_id,
        )
        if runtime_state is None:
            return self._build_skipped_stage_result(
                stage_name=stage_name,
                note_id=note_id,
                index_version=index_version,
                pipeline_run_id=pipeline_run_id,
                request_id=request_id,
                skipped_reason="missing_runtime_state",
            )

        if runtime_state.current_index_version != index_version:
            return self._build_skipped_stage_result(
                stage_name=stage_name,
                note_id=note_id,
                index_version=index_version,
                pipeline_run_id=pipeline_run_id,
                request_id=request_id,
                skipped_reason="stale_version",
            )

        if runtime_state.pipeline_run_note_id != note_id or runtime_state.pipeline_run_index_version != index_version:
            return self._build_skipped_stage_result(
                stage_name=stage_name,
                note_id=note_id,
                index_version=index_version,
                pipeline_run_id=pipeline_run_id,
                request_id=request_id,
                skipped_reason="snapshot_mismatch",
            )

        expected_snapshot_hash = compute_snapshot_hash(
            asset_ids=runtime_state.snapshot_asset_ids,
            link_ids=runtime_state.snapshot_link_ids,
        )
        if runtime_state.snapshot_hash != expected_snapshot_hash:
            return self._build_skipped_stage_result(
                stage_name=stage_name,
                note_id=note_id,
                index_version=index_version,
                pipeline_run_id=pipeline_run_id,
                request_id=request_id,
                skipped_reason="invalid_snapshot_hash",
            )

        snapshot_target_ids = snapshot_target_ids_getter(runtime_state)
        existing_target_ids = existing_target_ids_loader(snapshot_target_ids)
        filtered_target_ids = self._filter_snapshot_target_ids(
            stage_name=stage_name,
            note_id=note_id,
            index_version=index_version,
            pipeline_run_id=pipeline_run_id,
            request_id=request_id,
            candidate_target_ids=existing_target_ids,
            snapshot_target_ids=snapshot_target_ids,
        )
        existing_target_ids_set = set(filtered_target_ids)

        processed_count = 0
        skipped_count = 0
        for target_id in snapshot_target_ids:
            if target_id not in existing_target_ids_set:
                skipped_count += 1
                self._log_target_skip(
                    stage_name=stage_name,
                    note_id=note_id,
                    index_version=index_version,
                    pipeline_run_id=pipeline_run_id,
                    request_id=request_id,
                    target_id=target_id,
                    skipped_reason="missing_target",
                )
                continue
            processed_count += 1

        logger.info(
            "pipeline_stage_completed",
            extra={
                "event": "pipeline_stage_completed",
                "stage_name": stage_name,
                "note_id": str(note_id),
                "index_version": index_version,
                "request_id": request_id,
                "pipeline_run_id": str(pipeline_run_id),
                "processed_count": processed_count,
                "skipped_count": skipped_count,
            },
        )
        return {
            "stage_name": stage_name,
            "status": "done",
            "processed_count": processed_count,
            "skipped_count": skipped_count,
            "skipped": False,
        }

    def _filter_snapshot_target_ids(
        self,
        *,
        stage_name: str,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
        request_id: str | None,
        candidate_target_ids: list[UUID],
        snapshot_target_ids: list[UUID],
    ) -> list[UUID]:
        snapshot_target_ids_set = set(snapshot_target_ids)
        filtered_target_ids: list[UUID] = []
        for target_id in candidate_target_ids:
            if target_id not in snapshot_target_ids_set:
                self._log_target_skip(
                    stage_name=stage_name,
                    note_id=note_id,
                    index_version=index_version,
                    pipeline_run_id=pipeline_run_id,
                    request_id=request_id,
                    target_id=target_id,
                    skipped_reason="not_in_snapshot",
                )
                continue
            filtered_target_ids.append(target_id)
        return filtered_target_ids

    def _build_skipped_stage_result(
        self,
        *,
        stage_name: str,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
        request_id: str | None,
        skipped_reason: str,
    ) -> dict[str, object]:
        logger.info(
            "pipeline_stage_skipped",
            extra={
                "event": "pipeline_stage_skipped",
                "stage_name": stage_name,
                "note_id": str(note_id),
                "index_version": index_version,
                "request_id": request_id,
                "pipeline_run_id": str(pipeline_run_id),
                "skipped_reason": skipped_reason,
            },
        )
        return {
            "stage_name": stage_name,
            "status": "skipped",
            "skipped": True,
            "skipped_reason": skipped_reason,
            "processed_count": 0,
            "skipped_count": 0,
        }

    @staticmethod
    def _log_target_skip(
        *,
        stage_name: str,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
        request_id: str | None,
        target_id: UUID,
        skipped_reason: str,
    ) -> None:
        logger.info(
            "pipeline_stage_target_skipped",
            extra={
                "event": "pipeline_stage_target_skipped",
                "stage_name": stage_name,
                "note_id": str(note_id),
                "index_version": index_version,
                "request_id": request_id,
                "pipeline_run_id": str(pipeline_run_id),
                "target_id": str(target_id),
                "skipped_reason": skipped_reason,
            },
        )


def build_pipeline_orchestrator(*, session: Session) -> CeleryPipelineOrchestrator:
    return CeleryPipelineOrchestrator(
        runtime_repository=SqlAlchemyPipelineRuntimeRepository(session=session),
        settings=get_settings(),
        celery=celery_app,
    )


def build_pipeline_stage_runner(*, session: Session) -> PipelineStageRunner:
    return PipelineStageRunner(runtime_repository=SqlAlchemyPipelineRuntimeRepository(session=session))
