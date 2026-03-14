from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.infra.models import NoteTag, Tag


@dataclass(frozen=True)
class TagRecord:
    id: UUID
    name: str
    created_at: datetime
    notes_count: int


@dataclass(frozen=True)
class TagListRecord:
    items: list[TagRecord]
    total: int
    limit: int
    offset: int


class TagRepository(Protocol):
    def list_tags(self, *, q: str | None, limit: int, offset: int) -> TagListRecord: ...


class SqlAlchemyTagRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_tags(self, *, q: str | None, limit: int, offset: int) -> TagListRecord:
        note_count = func.count(NoteTag.note_id)
        normalized_query = (q or "").strip()

        statement = (
            select(
                Tag.id,
                Tag.name,
                Tag.created_at,
                note_count.label("notes_count"),
            )
            .outerjoin(NoteTag, NoteTag.tag_id == Tag.id)
            .group_by(Tag.id, Tag.name, Tag.created_at)
        )

        if normalized_query:
            statement = statement.order_by(
                case((Tag.name.ilike(f"%{normalized_query}%"), 0), else_=1).asc(),
                note_count.desc(),
                Tag.name.asc(),
                Tag.id.asc(),
            )
        else:
            statement = statement.order_by(note_count.desc(), Tag.name.asc(), Tag.id.asc())

        total = self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self._session.execute(statement.limit(limit).offset(offset)).all()

        return TagListRecord(
            items=[TagRecord(*row) for row in rows],
            total=int(total),
            limit=limit,
            offset=offset,
        )
