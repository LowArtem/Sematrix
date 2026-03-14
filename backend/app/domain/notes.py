from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Protocol
from uuid import UUID

from app.domain.note_content import parse_note_content
from app.domain.errors import NotFoundError
from app.domain.tags import normalize_tag_names
from app.infra.notes import NoteRecord, NoteRepository


HASHTAG_PATTERN = re.compile(r"(?<!\w)#([0-9A-Za-z_\u0400-\u04FF]+)")


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


class PipelineDispatcher(Protocol):
    def start_pipeline(self, *, note_id: UUID, index_version: int, request_id: str | None) -> None: ...


class NoteService:
    def __init__(
        self,
        note_repository: NoteRepository,
        pipeline_dispatcher: PipelineDispatcher,
    ) -> None:
        self._note_repository = note_repository
        self._pipeline_dispatcher = pipeline_dispatcher

    def create_note(self) -> NoteResult:
        return self._to_result(self._note_repository.create_note())

    def get_note(self, note_id: UUID) -> NoteResult:
        note = self._note_repository.get_note(note_id)
        if note is None:
            raise NotFoundError("Note not found")
        return self._to_result(note)

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
        save_result = self._note_repository.save_note(
            note_id=note_id,
            title=title.strip(),
            folder_id=folder_id,
            tag_names=tags,
            content_json=content_json,
            content_text_flat=parsed_content.content_text_flat,
            asset_ids=parsed_content.asset_ids,
            links=parsed_content.links,
        )

        if save_result.pipeline_started:
            self._pipeline_dispatcher.start_pipeline(
                note_id=save_result.note.id,
                index_version=save_result.note.index_version,
                request_id=request_id,
            )

        return NoteSaveOutcome(
            note=self._to_result(save_result.note),
            pipeline_started=save_result.pipeline_started,
        )

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
