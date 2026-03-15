from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Protocol
from uuid import UUID

from app.core import get_logger
from app.domain.note_lifecycle import has_meaningful_content
from app.domain.note_content import parse_note_content
from app.domain.pipeline import build_processing_warning, build_search_text
from app.domain.errors import NotFoundError
from app.domain.tags import TAG_NAME_PATTERN, normalize_tag_names
from app.infra.notes import DraftCleanupRecord, NoteRecord, NoteRepository


TAG_NAME_INNER_PATTERN = TAG_NAME_PATTERN.pattern.removeprefix("^").removesuffix("$")
HASHTAG_PATTERN = re.compile(rf"(?<!\w)#({TAG_NAME_INNER_PATTERN})(?=$|[^\w])")
logger = get_logger(__name__)


@dataclass(frozen=True)
class NoteResult:
    id: UUID
    created_at: datetime
    updated_at: datetime
    title: str
    summary: str
    folder_id: UUID | None
    tags: list[dict[str, Any]]
    content_json: dict[str, Any]
    status: str
    processing_error: str | None
    has_warnings: bool
    warnings_count: int
    processing_warnings: list[dict[str, Any]]
    index_version: int


@dataclass(frozen=True)
class NoteCardResult:
    id: UUID
    title: str
    summary: str
    updated_at: datetime
    tags: list[dict[str, Any]]
    folder_id: UUID | None
    status: str
    has_warnings: bool
    warnings_count: int
    score: float | None


@dataclass(frozen=True)
class NoteListResult:
    items: list[NoteCardResult]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class ParsedNoteQuery:
    text_query: str
    tag_names: list[str]


@dataclass(frozen=True)
class NoteSaveOutcome:
    note: NoteResult
    pipeline_started: bool


@dataclass(frozen=True)
class DraftCleanupResult:
    candidate_count: int
    deleted_draft_count: int
    deleted_asset_count: int
    deletion_errors: list[str]


class PipelineDispatcher(Protocol):
    def start_pipeline(self, *, note_id: UUID, index_version: int, request_id: str | None) -> None: ...


class NoteGenerationClient(Protocol):
    def generate_fast_summary(
        self,
        *,
        title: str,
        content_text_flat: str,
        tag_names: list[str],
    ) -> str: ...

    def generate_title(self, *, content_text_flat: str, tag_names: list[str]) -> str: ...


class NoteService:
    def __init__(
        self,
        note_repository: NoteRepository,
        pipeline_dispatcher: PipelineDispatcher,
        note_generation_client: NoteGenerationClient,
    ) -> None:
        self._note_repository = note_repository
        self._pipeline_dispatcher = pipeline_dispatcher
        self._note_generation_client = note_generation_client

    def create_note(self) -> NoteResult:
        return self._to_result(self._note_repository.create_note())

    def get_note(self, note_id: UUID) -> NoteResult:
        note = self._note_repository.get_note(note_id)
        if note is None:
            raise NotFoundError("Note not found")
        return self._to_result(note)

    def delete_note(self, note_id: UUID) -> None:
        self._note_repository.delete_note(note_id)

    def reindex_note(self, note_id: UUID, *, request_id: str | None) -> NoteResult:
        reindex_result = self._note_repository.reindex_note(note_id, request_id=request_id)
        logger.info(
            "note_processing_started",
            extra={
                "event": "note_processing_started",
                "note_id": str(reindex_result.note.id),
                "index_version": reindex_result.note.index_version,
                "request_id": request_id,
                "pipeline_run_id": str(reindex_result.pipeline_run.id),
                "started_at": reindex_result.pipeline_run.started_at.isoformat(),
            },
        )
        self._pipeline_dispatcher.start_pipeline(
            note_id=reindex_result.note.id,
            index_version=reindex_result.note.index_version,
            request_id=request_id,
        )
        return self._to_result(reindex_result.note)

    def list_notes(
        self,
        q: str | None,
        folder_id: UUID | None,
        limit: int,
        offset: int,
    ) -> NoteListResult:
        parsed_query = parse_note_query(q)
        result = self._note_repository.list_notes(
            text_query=parsed_query.text_query,
            tag_names=parsed_query.tag_names,
            folder_id=folder_id,
            limit=limit,
            offset=offset,
        )
        return NoteListResult(
            items=[self._to_card_result(note) for note in result.items],
            total=result.total,
            limit=result.limit,
            offset=result.offset,
        )

    def save_note(
        self,
        note_id: UUID,
        *,
        title: str,
        folder_id: UUID | None,
        tags: list[str],
        content_json: dict[str, Any],
        request_id: str | None,
    ) -> NoteSaveOutcome:
        parsed_content = parse_note_content(content_json)
        normalized_title = title.strip()
        should_start_processing = has_meaningful_content(
            content_text_flat=parsed_content.content_text_flat,
            asset_count=len(parsed_content.asset_ids),
            link_count=len(parsed_content.links),
        )
        effective_title = normalized_title
        fast_summary = ""
        processing_warnings: list[dict[str, object]] = []

        if should_start_processing:
            effective_title, title_warnings = self._resolve_title(
                note_id=note_id,
                title=normalized_title,
                content_text_flat=parsed_content.content_text_flat,
                tag_names=tags,
            )
            processing_warnings.extend(title_warnings)
            fast_summary, summary_warnings = self._build_fast_summary(
                note_id=note_id,
                title=effective_title,
                content_text_flat=parsed_content.content_text_flat,
                tag_names=tags,
            )
            processing_warnings.extend(summary_warnings)

        save_result = self._note_repository.save_note(
            note_id=note_id,
            title=effective_title,
            folder_id=folder_id,
            tag_names=tags,
            content_json=content_json,
            content_text_flat=parsed_content.content_text_flat,
            asset_ids=parsed_content.asset_ids,
            links=parsed_content.links,
            should_start_processing=should_start_processing,
            summary=fast_summary,
            processing_warnings=processing_warnings,
            request_id=request_id,
        )

        if save_result.pipeline_started:
            pipeline_run = save_result.pipeline_run
            if pipeline_run is None:
                raise RuntimeError("Pipeline run was not created for a processing save")
            logger.info(
                "note_processing_started",
                extra={
                    "event": "note_processing_started",
                    "note_id": str(save_result.note.id),
                    "index_version": save_result.note.index_version,
                    "request_id": request_id,
                    "pipeline_run_id": str(pipeline_run.id),
                    "started_at": pipeline_run.started_at.isoformat(),
                },
            )
            self._pipeline_dispatcher.start_pipeline(
                note_id=save_result.note.id,
                index_version=save_result.note.index_version,
                request_id=request_id,
            )

        return NoteSaveOutcome(
            note=self._to_result(save_result.note),
            pipeline_started=save_result.pipeline_started,
        )

    def _resolve_title(
        self,
        *,
        note_id: UUID,
        title: str,
        content_text_flat: str,
        tag_names: list[str],
    ) -> tuple[str, list[dict[str, object]]]:
        if title:
            return title, []

        try:
            generated_title = self._note_generation_client.generate_title(
                content_text_flat=content_text_flat,
                tag_names=tag_names,
            ).strip()
            if generated_title:
                return generated_title, []
            raise ValueError("Generated title was empty")
        except Exception as exc:
            fallback_title = build_title_fallback(content_text_flat)
            warning = build_processing_warning(
                stage="title_generation",
                target=str(note_id),
                code="title_generation_failed",
                message=str(exc),
                retryable=False,
            )
            return fallback_title, [warning]

    def _build_fast_summary(
        self,
        *,
        note_id: UUID,
        title: str,
        content_text_flat: str,
        tag_names: list[str],
    ) -> tuple[str, list[dict[str, object]]]:
        fast_summary_source = build_search_text(
            title=title,
            content_text_flat=content_text_flat,
            tag_names=tag_names,
            asset_texts=[],
            link_texts=[],
        )
        if not fast_summary_source:
            return "", []

        try:
            summary = self._note_generation_client.generate_fast_summary(
                title=title,
                content_text_flat=content_text_flat,
                tag_names=tag_names,
            ).strip()
            return summary, []
        except Exception as exc:
            warning = build_processing_warning(
                stage="summary_fast",
                target=str(note_id),
                code="summary_fast_failed",
                message=str(exc),
                retryable=False,
            )
            return "", [warning]

    @staticmethod
    def _to_result(note: NoteRecord) -> NoteResult:
        return NoteResult(
            id=note.id,
            created_at=note.created_at,
            updated_at=note.updated_at,
            title=note.title,
            summary=note.summary,
            folder_id=note.folder_id,
            tags=note.tags,
            content_json=note.content_json,
            status=note.status,
            processing_error=note.processing_error,
            has_warnings=note.has_warnings,
            warnings_count=note.warnings_count,
            processing_warnings=note.processing_warnings,
            index_version=note.index_version,
        )

    @staticmethod
    def _to_card_result(note: NoteRecord) -> NoteCardResult:
        return NoteCardResult(
            id=note.id,
            title=note.title,
            summary=note.summary,
            updated_at=note.updated_at,
            tags=note.tags,
            folder_id=note.folder_id,
            status=note.status,
            has_warnings=note.has_warnings,
            warnings_count=note.warnings_count,
            score=note.score,
        )


class DraftCleanupService:
    def __init__(self, note_repository: NoteRepository) -> None:
        self._note_repository = note_repository

    def cleanup_expired_empty_drafts(self, *, ttl_hours: int) -> DraftCleanupResult:
        cleanup_result = self._note_repository.cleanup_expired_empty_drafts(ttl_hours=ttl_hours)
        return self._to_cleanup_result(cleanup_result)

    @staticmethod
    def _to_cleanup_result(cleanup_result: DraftCleanupRecord) -> DraftCleanupResult:
        return DraftCleanupResult(
            candidate_count=cleanup_result.candidate_count,
            deleted_draft_count=cleanup_result.deleted_draft_count,
            deleted_asset_count=cleanup_result.deleted_asset_count,
            deletion_errors=cleanup_result.deletion_errors,
        )


def parse_note_query(q: str | None) -> ParsedNoteQuery:
    raw_query = (q or "").strip()
    if not raw_query:
        return ParsedNoteQuery(text_query="", tag_names=[])

    raw_tag_names = HASHTAG_PATTERN.findall(raw_query)
    normalized_tag_names = normalize_tag_names(raw_tag_names) if raw_tag_names else []
    text_query = HASHTAG_PATTERN.sub(" ", raw_query)
    normalized_text_query = " ".join(text_query.split())

    return ParsedNoteQuery(
        text_query=normalized_text_query,
        tag_names=normalized_tag_names,
    )


def build_title_fallback(content_text_flat: str, *, max_length: int = 120) -> str:
    for raw_line in content_text_flat.splitlines():
        normalized_line = " ".join(raw_line.split())
        if not normalized_line:
            continue
        if len(normalized_line) <= max_length:
            return normalized_line
        return f"{normalized_line[: max_length - 3].rstrip()}..."
    return ""
