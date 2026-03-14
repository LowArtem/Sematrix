from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from collections.abc import Iterable
from uuid import UUID

from app.infra.tags import TagListRecord, TagRecord, TagRepository


TAG_NAME_PATTERN = re.compile(r"^[0-9A-Za-zА-Яа-яЁё_]+$")


@dataclass(frozen=True)
class TagResult:
    id: UUID
    name: str
    normalized_name: str
    created_at: datetime
    notes_count: int


@dataclass(frozen=True)
class TagListResult:
    items: list[TagResult]
    total: int
    limit: int
    offset: int


class TagService:
    def __init__(self, tag_repository: TagRepository) -> None:
        self._tag_repository = tag_repository

    def list_tags(self, *, q: str | None, limit: int, offset: int) -> TagListResult:
        result = self._tag_repository.list_tags(q=q, limit=limit, offset=offset)
        return TagListResult(
            items=[self._to_result(tag) for tag in result.items],
            total=result.total,
            limit=result.limit,
            offset=result.offset,
        )

    @staticmethod
    def _to_result(tag: TagRecord) -> TagResult:
        return TagResult(
            id=tag.id,
            name=tag.name,
            normalized_name=tag.name,
            created_at=tag.created_at,
            notes_count=tag.notes_count,
        )


def normalize_tag_name(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Tag name cannot be empty")
    if any(character.isspace() for character in normalized):
        raise ValueError("Tag name cannot contain spaces")
    if not TAG_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Tag name may contain only Latin/Cyrillic letters, digits, and underscore"
        )
    return normalized


def normalize_tag_names(values: Iterable[str]) -> list[str]:
    normalized_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = normalize_tag_name(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_values.append(normalized)

    return normalized_values
