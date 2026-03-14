from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.infra.models import Note


EMPTY_DOCUMENT = {"type": "doc", "content": []}


@dataclass(frozen=True)
class NoteRecord:
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


class NoteRepository(Protocol):
    def create_note(self) -> NoteRecord: ...


class SqlAlchemyNoteRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_note(self) -> NoteRecord:
        note = Note(content_json=EMPTY_DOCUMENT)
        self._session.add(note)
        self._session.commit()
        self._session.refresh(note)
        return self._to_record(note)

    @staticmethod
    def _to_record(note: Note) -> NoteRecord:
        return NoteRecord(
            id=note.id,
            created_at=note.created_at,
            updated_at=note.updated_at,
            title=note.title,
            summary=note.summary,
            folder_id=note.folder_id,
            tags=[{"id": tag.id, "name": tag.name} for tag in note.tags],
            content_json=note.content_json,
            status=note.status,
            processing_error=note.processing_error,
            has_warnings=note.has_warnings,
            warnings_count=note.warnings_count,
            processing_warnings=note.processing_warnings,
            index_version=note.index_version,
        )
