from __future__ import annotations

from datetime import datetime
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Computed, DateTime, Enum, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db import Base


NOTE_STATUS_VALUES = ("Draft", "Processing", "Ready", "Error")
SEARCH_TSV_EXPRESSION = (
    "to_tsvector('russian', coalesce(search_text, '')) "
    "|| to_tsvector('english', coalesce(search_text, ''))"
)


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    notes: Mapped[list["Note"]] = relationship(back_populates="folder")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
    )
    content_json: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{\"type\": \"doc\", \"content\": []}'::jsonb"),
    )
    content_text_flat: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(
        Enum(*NOTE_STATUS_VALUES, name="note_status", native_enum=True),
        nullable=False,
        server_default=text("'Draft'"),
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_warnings: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    warnings_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    processing_warnings: Mapped[list[object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    index_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    search_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    search_tsv: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed(SEARCH_TSV_EXPRESSION, persisted=True),
        nullable=False,
    )
    embedding: Mapped[object | None] = mapped_column(Vector(1024), nullable=True)

    folder: Mapped[Folder | None] = relationship(back_populates="notes")
    tags: Mapped[list["Tag"]] = relationship(secondary="note_tags", back_populates="notes")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    notes: Mapped[list[Note]] = relationship(secondary="note_tags", back_populates="tags")


class NoteTag(Base):
    __tablename__ = "note_tags"

    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
