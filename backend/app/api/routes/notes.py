from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response, status
from uuid import UUID

from app.api.dependencies import get_note_service
from app.api.dto import AsyncAcceptedDto, NoteCardDto, NoteDetailDto, NoteSaveRequestDto, PaginatedResponse, TagRefDto
from app.domain.notes import NoteCardResult, NoteListResult, NoteResult, NoteSaveOutcome, NoteService


api_notes_router = APIRouter(prefix="/notes", tags=["notes"])


@api_notes_router.post("", response_model=NoteDetailDto, status_code=status.HTTP_201_CREATED)
def create_note(service: NoteService = Depends(get_note_service)) -> NoteDetailDto:
    return _to_note_detail_dto(service.create_note())


@api_notes_router.get("", response_model=PaginatedResponse[NoteCardDto])
def list_notes(
    q: str | None = Query(default=None),
    folder_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=0),
    offset: int = Query(default=0, ge=0),
    service: NoteService = Depends(get_note_service),
) -> PaginatedResponse[NoteCardDto]:
    return _to_note_list_dto(service.list_notes(q=q, folder_id=folder_id, limit=limit, offset=offset))


@api_notes_router.get("/{note_id}", response_model=NoteDetailDto)
def get_note(note_id: UUID, service: NoteService = Depends(get_note_service)) -> NoteDetailDto:
    return _to_note_detail_dto(service.get_note(note_id))


@api_notes_router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: UUID, service: NoteService = Depends(get_note_service)) -> Response:
    service.delete_note(note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_notes_router.post(
    "/{note_id}/reindex",
    response_model=AsyncAcceptedDto,
    status_code=status.HTTP_202_ACCEPTED,
)
def reindex_note(
    note_id: UUID,
    request: Request,
    service: NoteService = Depends(get_note_service),
) -> AsyncAcceptedDto:
    note = service.reindex_note(note_id, request_id=getattr(request.state, "request_id", None))
    return AsyncAcceptedDto(
        id=note.id,
        status=note.status,
        index_version=note.index_version,
        message="Note reindex accepted and processing started",
    )


@api_notes_router.patch(
    "/{note_id}",
    response_model=NoteDetailDto | AsyncAcceptedDto,
    responses={status.HTTP_202_ACCEPTED: {"model": AsyncAcceptedDto}},
)
def save_note(
    note_id: UUID,
    payload: NoteSaveRequestDto,
    request: Request,
    response: Response,
    service: NoteService = Depends(get_note_service),
) -> NoteDetailDto | AsyncAcceptedDto:
    outcome = service.save_note(
        note_id,
        title=payload.title,
        folder_id=payload.folder_id,
        tags=payload.tags,
        content_json=payload.content_json,
        request_id=getattr(request.state, "request_id", None),
    )
    return _to_note_save_response(outcome=outcome, response=response)


def _to_note_list_dto(note_list: NoteListResult) -> PaginatedResponse[NoteCardDto]:
    return PaginatedResponse[NoteCardDto](
        items=[_to_note_card_dto(note) for note in note_list.items],
        total=note_list.total,
        limit=note_list.limit,
        offset=note_list.offset,
    )


def _to_note_card_dto(note: NoteCardResult) -> NoteCardDto:
    return NoteCardDto(
        id=note.id,
        title=note.title,
        summary=note.summary,
        updated_at=note.updated_at,
        tags=[TagRefDto.model_validate(tag) for tag in note.tags],
        folder_id=note.folder_id,
        status=note.status,
        has_warnings=note.has_warnings,
        warnings_count=note.warnings_count,
        score=note.score,
    )


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


def _to_note_save_response(
    *,
    outcome: NoteSaveOutcome,
    response: Response,
) -> NoteDetailDto | AsyncAcceptedDto:
    if outcome.pipeline_started:
        response.status_code = status.HTTP_202_ACCEPTED
        return AsyncAcceptedDto(
            id=outcome.note.id,
            status=outcome.note.status,
            index_version=outcome.note.index_version,
            message="Note save accepted and processing started",
        )

    response.status_code = status.HTTP_200_OK
    return _to_note_detail_dto(outcome.note)
