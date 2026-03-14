from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.models import Folder, Note


@dataclass(frozen=True)
class FolderRecord:
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    notes_count: int


class FolderRepository(Protocol):
    def list_folders(self, q: str | None = None) -> list[FolderRecord]: ...

    def create_folder(self, name: str) -> FolderRecord: ...

    def rename_folder(self, folder_id: UUID, name: str) -> FolderRecord: ...

    def delete_folder(self, folder_id: UUID) -> None: ...


class SqlAlchemyFolderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_folders(self, q: str | None = None) -> list[FolderRecord]:
        note_count = func.count(Note.id)
        statement = (
            select(
                Folder.id,
                Folder.name,
                Folder.created_at,
                Folder.updated_at,
                note_count.label("notes_count"),
            )
            .outerjoin(Note, Note.folder_id == Folder.id)
            .group_by(Folder.id, Folder.name, Folder.created_at, Folder.updated_at)
            .order_by(Folder.name.asc(), Folder.id.asc())
        )

        if q and q.strip():
            statement = statement.where(Folder.name.ilike(f"%{q.strip()}%"))

        rows = self._session.execute(statement).all()
        return [FolderRecord(*row) for row in rows]

    def create_folder(self, name: str) -> FolderRecord:
        folder = Folder(name=name)
        self._session.add(folder)

        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("folder_conflict") from exc

        self._session.refresh(folder)
        return self._to_record(folder, notes_count=0)

    def rename_folder(self, folder_id: UUID, name: str) -> FolderRecord:
        folder = self._session.get(Folder, folder_id)
        if folder is None:
            raise LookupError("folder_not_found")

        folder.name = name
        folder.updated_at = datetime.now(timezone.utc)

        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("folder_conflict") from exc

        self._session.refresh(folder)
        return self._to_record(folder, notes_count=self._count_notes(folder.id))

    def delete_folder(self, folder_id: UUID) -> None:
        folder = self._session.get(Folder, folder_id)
        if folder is None:
            raise LookupError("folder_not_found")

        self._session.delete(folder)
        self._session.commit()

    def _count_notes(self, folder_id: UUID) -> int:
        statement = select(func.count(Note.id)).where(Note.folder_id == folder_id)
        return int(self._session.scalar(statement) or 0)

    @staticmethod
    def _to_record(folder: Folder, notes_count: int) -> FolderRecord:
        return FolderRecord(
            id=folder.id,
            name=folder.name,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
            notes_count=notes_count,
        )
