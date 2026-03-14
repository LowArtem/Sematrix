from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.infra.models import Note, NoteTag, Tag


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
    score: float | None = None


@dataclass(frozen=True)
class NoteListRecord:
    items: list[NoteRecord]
    total: int
    limit: int
    offset: int


class NoteRepository(Protocol):
    def create_note(self) -> NoteRecord: ...

    def get_note(self, note_id: UUID) -> NoteRecord | None: ...

    def list_notes(
        self,
        *,
        text_query: str,
        tag_names: list[str],
        folder_id: UUID | None,
        limit: int,
        offset: int,
    ) -> NoteListRecord: ...


class SqlAlchemyNoteRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_note(self) -> NoteRecord:
        note = Note(content_json=EMPTY_DOCUMENT)
        self._session.add(note)
        self._session.commit()
        self._session.refresh(note)
        return self._to_record(note)

    def get_note(self, note_id: UUID) -> NoteRecord | None:
        note = self._session.get(Note, note_id)
        if note is None:
            return None
        return self._to_record(note)

    def list_notes(
        self,
        *,
        text_query: str,
        tag_names: list[str],
        folder_id: UUID | None,
        limit: int,
        offset: int,
    ) -> NoteListRecord:
        note_ids_query = select(Note.id)

        if folder_id is not None:
            note_ids_query = note_ids_query.where(Note.folder_id == folder_id)

        if text_query:
            pattern = f"%{text_query}%"
            note_ids_query = note_ids_query.where(
                or_(
                    Note.title.ilike(pattern),
                    Note.summary.ilike(pattern),
                    Note.search_text.ilike(pattern),
                    Note.content_text_flat.ilike(pattern),
                )
            )

        if tag_names:
            note_ids_query = (
                note_ids_query.join(NoteTag, NoteTag.note_id == Note.id)
                .join(Tag, Tag.id == NoteTag.tag_id)
                .where(Tag.name.in_(tag_names))
                .group_by(Note.id)
                .having(func.count(func.distinct(Tag.name)) == len(tag_names))
            )

        note_ids_subquery = note_ids_query.subquery()
        total = self._session.scalar(select(func.count()).select_from(note_ids_subquery)) or 0

        notes = list(
            self._session.scalars(
                select(Note)
                .where(Note.id.in_(select(note_ids_subquery.c.id)))
                .options(selectinload(Note.tags))
                .order_by(Note.updated_at.desc(), Note.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )

        return NoteListRecord(
            items=[self._to_record(note) for note in notes],
            total=total,
            limit=limit,
            offset=offset,
        )

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
