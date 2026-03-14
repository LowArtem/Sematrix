from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.errors import ConflictError, NotFoundError
from app.infra.folders import FolderRecord, FolderRepository


@dataclass(frozen=True)
class FolderResult:
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    notes_count: int


class FolderService:
    def __init__(self, folder_repository: FolderRepository) -> None:
        self._folder_repository = folder_repository

    def list_folders(self, q: str | None = None) -> list[FolderResult]:
        return [self._to_result(folder) for folder in self._folder_repository.list_folders(q=q)]

    def create_folder(self, name: str) -> FolderResult:
        try:
            folder = self._folder_repository.create_folder(name=name)
        except ValueError as exc:
            raise ConflictError(f"Folder '{name}' already exists") from exc

        return self._to_result(folder)

    def rename_folder(self, folder_id: UUID, name: str) -> FolderResult:
        try:
            folder = self._folder_repository.rename_folder(folder_id=folder_id, name=name)
        except LookupError as exc:
            raise NotFoundError("Folder not found") from exc
        except ValueError as exc:
            raise ConflictError(f"Folder '{name}' already exists") from exc

        return self._to_result(folder)

    def delete_folder(self, folder_id: UUID) -> None:
        try:
            self._folder_repository.delete_folder(folder_id=folder_id)
        except LookupError as exc:
            raise NotFoundError("Folder not found") from exc

    @staticmethod
    def _to_result(folder: FolderRecord) -> FolderResult:
        return FolderResult(
            id=folder.id,
            name=folder.name,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
            notes_count=folder.notes_count,
        )
