from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.errors import NotFoundError
from app.infra.notes import NoteRecord, NoteRepository


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


class NoteService:
    def __init__(self, note_repository: NoteRepository) -> None:
        self._note_repository = note_repository

    def create_note(self) -> NoteResult:
        return self._to_result(self._note_repository.create_note())

    def get_note(self, note_id: UUID) -> NoteResult:
        note = self._note_repository.get_note(note_id)
        if note is None:
            raise NotFoundError("Note not found")
        return self._to_result(note)

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
