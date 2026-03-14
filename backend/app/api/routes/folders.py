from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_folder_service
from app.api.dto import FolderCreateRequestDto, FolderDto, FolderUpdateRequestDto
from app.domain.folders import FolderResult, FolderService


api_folders_router = APIRouter(prefix="/folders", tags=["folders"])


@api_folders_router.get("", response_model=list[FolderDto])
def list_folders(
    q: str | None = None,
    service: FolderService = Depends(get_folder_service),
) -> list[FolderDto]:
    return [_to_folder_dto(folder) for folder in service.list_folders(q=q)]


@api_folders_router.post("", response_model=FolderDto, status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: FolderCreateRequestDto,
    service: FolderService = Depends(get_folder_service),
) -> FolderDto:
    return _to_folder_dto(service.create_folder(name=payload.name))


@api_folders_router.patch("/{folder_id}", response_model=FolderDto)
def rename_folder(
    folder_id: UUID,
    payload: FolderUpdateRequestDto,
    service: FolderService = Depends(get_folder_service),
) -> FolderDto:
    return _to_folder_dto(service.rename_folder(folder_id=folder_id, name=payload.name))


@api_folders_router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: UUID,
    service: FolderService = Depends(get_folder_service),
) -> Response:
    service.delete_folder(folder_id=folder_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_folder_dto(folder: FolderResult) -> FolderDto:
    return FolderDto(
        id=folder.id,
        name=folder.name,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
        notes_count=folder.notes_count,
    )
