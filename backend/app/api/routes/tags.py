from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_tag_service
from app.api.dto import PaginatedResponse, TagDto
from app.domain.tags import TagListResult, TagResult, TagService


api_tags_router = APIRouter(prefix="/tags", tags=["tags"])


@api_tags_router.get("", response_model=PaginatedResponse[TagDto])
def list_tags(
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=0),
    offset: int = Query(default=0, ge=0),
    service: TagService = Depends(get_tag_service),
) -> PaginatedResponse[TagDto]:
    return _to_tag_list_dto(service.list_tags(q=q, limit=limit, offset=offset))


def _to_tag_list_dto(tag_list: TagListResult) -> PaginatedResponse[TagDto]:
    return PaginatedResponse[TagDto](
        items=[_to_tag_dto(tag) for tag in tag_list.items],
        total=tag_list.total,
        limit=tag_list.limit,
        offset=tag_list.offset,
    )


def _to_tag_dto(tag: TagResult) -> TagDto:
    return TagDto(
        id=tag.id,
        name=tag.name,
        normalized_name=tag.normalized_name,
        notes_count=tag.notes_count,
    )
