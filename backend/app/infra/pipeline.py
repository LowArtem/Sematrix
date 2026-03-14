from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable, Protocol
from uuid import UUID

from celery import chord, group
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core import Settings, get_logger, get_settings
from app.domain.pipeline import build_pipeline_stages, build_search_text, compute_snapshot_hash
from app.infra.models import AssetProcessingResult, LinkProcessingResult, Note, NoteAsset, NoteLink, PipelineRun
from app.infra.ollama import OllamaClient
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


@dataclass(frozen=True)
class PipelineFinalizationRuntimeState:
    note_id: UUID
    index_version: int
    current_index_version: int
    pipeline_run_id: UUID
    pipeline_run_note_id: UUID
    pipeline_run_index_version: int
    started_at: datetime
    title: str
    content_text_flat: str
    tag_names: list[str]


@dataclass(frozen=True)
class AssetProcessingTextResult:
    ocr_text: str
    caption_text: str


@dataclass(frozen=True)
class LinkProcessingTextResult:
    url: str
    page_title: str
    extracted_text: str
    generated_summary: str


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

    def get_finalization_runtime_state(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
    ) -> PipelineFinalizationRuntimeState | None: ...

    def list_asset_processing_texts(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
    ) -> list[AssetProcessingTextResult]: ...

    def list_link_processing_texts(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
    ) -> list[LinkProcessingTextResult]: ...

    def finalize_pipeline_run(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
        search_text: str,
        embedding: list[float],
        summary: str,
        total_duration_ms: int,
        stage_durations_ms: dict[str, int],
    ) -> None: ...


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

    def get_finalization_runtime_state(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
    ) -> PipelineFinalizationRuntimeState | None:
        note = self._session.scalar(
            select(Note)
            .where(Note.id == note_id)
            .options(selectinload(Note.tags))
        )
        if note is None:
            return None

        pipeline_run = self._session.get(PipelineRun, pipeline_run_id)
        if pipeline_run is None:
            return None

        return PipelineFinalizationRuntimeState(
            note_id=note_id,
            index_version=index_version,
            current_index_version=note.index_version,
            pipeline_run_id=pipeline_run.id,
            pipeline_run_note_id=pipeline_run.note_id,
            pipeline_run_index_version=pipeline_run.index_version,
            started_at=pipeline_run.started_at,
            title=note.title,
            content_text_flat=note.content_text_flat,
            tag_names=[tag.name for tag in note.tags],
        )

    def list_asset_processing_texts(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
    ) -> list[AssetProcessingTextResult]:
        results = list(
            self._session.scalars(
                select(AssetProcessingResult)
                .where(
                    AssetProcessingResult.note_id == note_id,
                    AssetProcessingResult.index_version == index_version,
                    AssetProcessingResult.pipeline_run_id == pipeline_run_id,
                )
                .order_by(AssetProcessingResult.asset_id)
            )
        )
        return [
            AssetProcessingTextResult(
                ocr_text=result.ocr_text,
                caption_text=result.caption_text,
            )
            for result in results
        ]

    def list_link_processing_texts(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
    ) -> list[LinkProcessingTextResult]:
        rows = self._session.execute(
            select(LinkProcessingResult, NoteLink.url)
            .join(NoteLink, NoteLink.id == LinkProcessingResult.link_id)
            .where(
                LinkProcessingResult.note_id == note_id,
                LinkProcessingResult.index_version == index_version,
                LinkProcessingResult.pipeline_run_id == pipeline_run_id,
            )
            .order_by(LinkProcessingResult.link_id)
        ).all()
        return [
            LinkProcessingTextResult(
                url=url,
                page_title=result.page_title,
                extracted_text=result.extracted_text,
                generated_summary=result.generated_summary,
            )
            for result, url in rows
        ]

    def finalize_pipeline_run(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
        search_text: str,
        embedding: list[float],
        summary: str,
        total_duration_ms: int,
        stage_durations_ms: dict[str, int],
    ) -> None:
        note = self._session.get(Note, note_id)
        pipeline_run = self._session.get(PipelineRun, pipeline_run_id)
        if note is None or pipeline_run is None:
            raise RuntimeError("Pipeline finalization state disappeared before commit")
        if note.index_version != index_version:
            raise RuntimeError("Pipeline finalization attempted to write a stale note version")
        if pipeline_run.note_id != note_id or pipeline_run.index_version != index_version:
            raise RuntimeError("Pipeline finalization attempted to write a mismatched pipeline run")

        finished_at = datetime.now(timezone.utc)

        note.search_text = search_text
        note.embedding = embedding
        note.summary = summary
        note.status = "Ready"
        note.processing_error = None

        pipeline_run.status = "Ready"
        pipeline_run.finished_at = finished_at
        pipeline_run.total_duration_ms = total_duration_ms
        pipeline_run.stage_durations_ms = stage_durations_ms
        pipeline_run.processing_error = None

        self._session.add(note)
        self._session.add(pipeline_run)
        self._session.commit()


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


class PipelineFinalizer:
    def __init__(
        self,
        *,
        runtime_repository: PipelineRuntimeRepository,
        ollama_client: OllamaClient,
    ) -> None:
        self._runtime_repository = runtime_repository
        self._ollama_client = ollama_client

    def finalize_pipeline(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
        request_id: str | None,
        stage_results: list[dict[str, object]],
    ) -> dict[str, object]:
        runtime_state = self._runtime_repository.get_finalization_runtime_state(
            note_id=note_id,
            index_version=index_version,
            pipeline_run_id=pipeline_run_id,
        )
        if runtime_state is None:
            return self._build_skipped_result(
                note_id=note_id,
                index_version=index_version,
                pipeline_run_id=pipeline_run_id,
                request_id=request_id,
                skipped_reason="missing_runtime_state",
            )

        if runtime_state.current_index_version != index_version:
            return self._build_skipped_result(
                note_id=note_id,
                index_version=index_version,
                pipeline_run_id=pipeline_run_id,
                request_id=request_id,
                skipped_reason="stale_version",
            )

        if runtime_state.pipeline_run_note_id != note_id or runtime_state.pipeline_run_index_version != index_version:
            return self._build_skipped_result(
                note_id=note_id,
                index_version=index_version,
                pipeline_run_id=pipeline_run_id,
                request_id=request_id,
                skipped_reason="pipeline_run_mismatch",
            )

        asset_text_results = self._runtime_repository.list_asset_processing_texts(
            note_id=note_id,
            index_version=index_version,
            pipeline_run_id=pipeline_run_id,
        )
        link_text_results = self._runtime_repository.list_link_processing_texts(
            note_id=note_id,
            index_version=index_version,
            pipeline_run_id=pipeline_run_id,
        )

        search_document_started_at = perf_counter()
        search_text = build_search_text(
            title=runtime_state.title,
            content_text_flat=runtime_state.content_text_flat,
            tag_names=runtime_state.tag_names,
            asset_texts=[
                text
                for result in asset_text_results
                for text in (result.ocr_text, result.caption_text)
            ],
            link_texts=[
                text
                for result in link_text_results
                for text in (result.url, result.page_title, result.extracted_text, result.generated_summary)
            ],
        )
        search_document_duration_ms = int((perf_counter() - search_document_started_at) * 1000)

        embeddings_started_at = perf_counter()
        embedding = self._ollama_client.embed_text(text=search_text)
        embeddings_duration_ms = int((perf_counter() - embeddings_started_at) * 1000)
        if len(embedding) != 1024:
            raise ValueError("Embedding dimensionality must be exactly 1024")

        summary_started_at = perf_counter()
        summary = self._ollama_client.generate_summary(search_text=search_text) if search_text else ""
        summary_duration_ms = int((perf_counter() - summary_started_at) * 1000)

        stage_durations_ms = self._build_stage_durations(
            stage_results=stage_results,
            search_document_duration_ms=search_document_duration_ms,
            embeddings_duration_ms=embeddings_duration_ms,
            summary_duration_ms=summary_duration_ms,
        )
        total_duration_ms = max(
            int((datetime.now(timezone.utc) - runtime_state.started_at).total_seconds() * 1000),
            0,
        )

        self._runtime_repository.finalize_pipeline_run(
            note_id=note_id,
            index_version=index_version,
            pipeline_run_id=pipeline_run_id,
            search_text=search_text,
            embedding=embedding,
            summary=summary,
            total_duration_ms=total_duration_ms,
            stage_durations_ms=stage_durations_ms,
        )

        logger.info(
            "note_processing_finished",
            extra={
                "event": "note_processing_finished",
                "note_id": str(note_id),
                "index_version": index_version,
                "request_id": request_id,
                "pipeline_run_id": str(pipeline_run_id),
                "status": "Ready",
                "total_duration_ms": total_duration_ms,
                "stage_durations_ms": stage_durations_ms,
            },
        )

        return {
            "status": "ready",
            "note_id": str(note_id),
            "index_version": index_version,
            "pipeline_run_id": str(pipeline_run_id),
            "search_text": search_text,
            "summary": summary,
            "total_duration_ms": total_duration_ms,
            "stage_durations_ms": stage_durations_ms,
        }

    def _build_skipped_result(
        self,
        *,
        note_id: UUID,
        index_version: int,
        pipeline_run_id: UUID,
        request_id: str | None,
        skipped_reason: str,
    ) -> dict[str, object]:
        logger.info(
            "pipeline_finalization_skipped",
            extra={
                "event": "pipeline_finalization_skipped",
                "note_id": str(note_id),
                "index_version": index_version,
                "request_id": request_id,
                "pipeline_run_id": str(pipeline_run_id),
                "status": "skipped",
                "processing_error": skipped_reason,
            },
        )
        return {
            "status": "skipped",
            "note_id": str(note_id),
            "index_version": index_version,
            "pipeline_run_id": str(pipeline_run_id),
            "skipped_reason": skipped_reason,
        }

    @staticmethod
    def _build_stage_durations(
        *,
        stage_results: list[dict[str, object]],
        search_document_duration_ms: int,
        embeddings_duration_ms: int,
        summary_duration_ms: int,
    ) -> dict[str, int]:
        stage_durations_ms: dict[str, int] = {
            "search_document_build": search_document_duration_ms,
            "embeddings": embeddings_duration_ms,
            "summary_final": summary_duration_ms,
        }

        stage_name_map = {
            "process_links": "link_fetch",
            "process_ocr": "ocr",
            "process_image_caption": "image_caption",
        }
        for stage_result in stage_results:
            raw_stage_name = stage_result.get("stage_name")
            raw_duration = stage_result.get("duration_ms")
            if not isinstance(raw_stage_name, str) or not isinstance(raw_duration, int):
                continue
            normalized_stage_name = stage_name_map.get(raw_stage_name, raw_stage_name)
            stage_durations_ms[normalized_stage_name] = raw_duration

        return stage_durations_ms


def build_pipeline_orchestrator(*, session: Session) -> CeleryPipelineOrchestrator:
    return CeleryPipelineOrchestrator(
        runtime_repository=SqlAlchemyPipelineRuntimeRepository(session=session),
        settings=get_settings(),
        celery=celery_app,
    )


def build_pipeline_stage_runner(*, session: Session) -> PipelineStageRunner:
    return PipelineStageRunner(runtime_repository=SqlAlchemyPipelineRuntimeRepository(session=session))


def build_pipeline_finalizer(*, session: Session) -> PipelineFinalizer:
    settings = get_settings()
    return PipelineFinalizer(
        runtime_repository=SqlAlchemyPipelineRuntimeRepository(session=session),
        ollama_client=OllamaClient(
            base_url=settings.ollama_url,
            llm_model=settings.llm_model,
            embed_model=settings.embed_model,
        ),
    )
