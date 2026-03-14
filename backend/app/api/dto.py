from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.tags import normalize_tag_names


class ApiErrorDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: Any | None = None


class TagRefDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str


ItemT = TypeVar("ItemT")


class PaginatedResponse(BaseModel, Generic[ItemT]):
    model_config = ConfigDict(extra="forbid")

    items: list[ItemT]
    total: int = Field(ge=0)
    limit: int = Field(ge=0)
    offset: int = Field(ge=0)


class AsyncAcceptedDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: str
    index_version: int = Field(ge=0)
    message: str


class NoteCardDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    summary: str
    updated_at: datetime
    tags: list[TagRefDto]
    folder_id: UUID | None = None
    status: str
    has_warnings: bool
    warnings_count: int = Field(ge=0)
    score: float | None = None


class NoteDetailDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    created_at: datetime
    updated_at: datetime
    title: str
    summary: str
    folder_id: UUID | None = None
    tags: list[TagRefDto]
    content_json: dict[str, Any]
    status: str
    processing_error: str | None = None
    has_warnings: bool
    warnings_count: int = Field(ge=0)
    processing_warnings: list[dict[str, Any]]
    index_version: int = Field(ge=0)


class FolderDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    notes_count: int | None = Field(default=None, ge=0)


class TagDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    normalized_name: str
    notes_count: int | None = Field(default=None, ge=0)


class AssetDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    mime_type: str
    size_bytes: int = Field(ge=0)
    url: str


class FolderCreateRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Folder name cannot be empty")
        return normalized


class FolderUpdateRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Folder name cannot be empty")
        return normalized


class NoteSaveRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    folder_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)
    content_json: dict[str, Any]

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return normalize_tag_names(value)
