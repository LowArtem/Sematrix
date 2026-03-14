from __future__ import annotations

from fastapi import APIRouter, Depends, status
from uuid import UUID

from app.api.dependencies import get_note_service
from app.api.dto import NoteDetailDto, TagRefDto
from app.domain.notes import NoteResult, NoteService


api_notes_router = APIRouter(prefix="/notes", tags=["notes"])


@api_notes_router.post("", response_model=NoteDetailDto, status_code=status.HTTP_201_CREATED)
def create_note(service: NoteService = Depends(get_note_service)) -> NoteDetailDto:
    return _to_note_detail_dto(service.create_note())


@api_notes_router.get("/{note_id}", response_model=NoteDetailDto)
def get_note(note_id: UUID, service: NoteService = Depends(get_note_service)) -> NoteDetailDto:
    return _to_note_detail_dto(service.get_note(note_id))


def _to_note_detail_dto(note: NoteResult) -> NoteDetailDto:
    return NoteDetailDto(
        id=note.id,
        created_at=note.created_at,
        updated_at=note.updated_at,
        title=note.title,
        summary=note.summary,
        folder_id=note.folder_id,
        tags=[TagRefDto.model_validate(tag) for tag in note.tags],
        content_json=note.content_json,
        status=note.status,
        processing_error=note.processing_error,
        has_warnings=note.has_warnings,
        warnings_count=note.warnings_count,
        processing_warnings=note.processing_warnings,
        index_version=note.index_version,
    )
