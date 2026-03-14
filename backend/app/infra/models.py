from __future__ import annotations

from datetime import datetime
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db import Base


NOTE_STATUS_VALUES = ("Draft", "Processing", "Ready", "Error")
PIPELINE_RUN_STATUS_VALUES = ("Processing", "Ready", "Error")
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
    __table_args__ = (
        Index("ix_notes_folder_id_updated_at_id", "folder_id", "updated_at", "id"),
        Index("ix_notes_search_tsv", "search_tsv", postgresql_using="gin"),
    )

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
    assets: Mapped[list["Asset"]] = relationship(secondary="note_assets", back_populates="notes")
    asset_processing_results: Mapped[list["AssetProcessingResult"]] = relationship(
        back_populates="note"
    )
    link_processing_results: Mapped[list["LinkProcessingResult"]] = relationship(
        back_populates="note"
    )
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(back_populates="note")
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


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_ext: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    notes: Mapped[list[Note]] = relationship(secondary="note_assets", back_populates="assets")
    processing_results: Mapped[list["AssetProcessingResult"]] = relationship(
        back_populates="asset"
    )


class NoteTag(Base):
    __tablename__ = "note_tags"
    __table_args__ = (Index("ix_note_tags_tag_id_note_id", "tag_id", "note_id"),)

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


class NoteAsset(Base):
    __tablename__ = "note_assets"
    __table_args__ = (Index("ix_note_assets_asset_id_note_id", "asset_id", "note_id"),)

    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (UniqueConstraint("note_id", "index_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
    )
    index_version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_asset_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default=text("'{}'::uuid[]"),
    )
    snapshot_link_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default=text("'{}'::uuid[]"),
    )
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*PIPELINE_RUN_STATUS_VALUES, name="pipeline_run_status", native_enum=True),
        nullable=False,
        server_default=text("'Processing'"),
    )
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage_durations_ms: Mapped[dict[str, int]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset_processing_results: Mapped[list["AssetProcessingResult"]] = relationship(
        back_populates="pipeline_run"
    )
    link_processing_results: Mapped[list["LinkProcessingResult"]] = relationship(
        back_populates="pipeline_run"
    )
    note: Mapped[Note] = relationship(back_populates="pipeline_runs")


class AssetProcessingResult(Base):
    __tablename__ = "asset_processing_results"
    __table_args__ = (
        UniqueConstraint("pipeline_run_id", "asset_id"),
        Index("ix_asset_processing_results_note_id_index_version", "note_id", "index_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    index_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    caption_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    ocr_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'pending'"))
    caption_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'pending'"),
    )
    warnings: Mapped[list[object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
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

    asset: Mapped[Asset] = relationship(back_populates="processing_results")
    note: Mapped[Note] = relationship(back_populates="asset_processing_results")
    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="asset_processing_results")


class LinkProcessingResult(Base):
    __tablename__ = "link_processing_results"
    __table_args__ = (
        UniqueConstraint("pipeline_run_id", "link_id"),
        Index("ix_link_processing_results_note_id_index_version", "note_id", "index_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
    )
    link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    index_version: Mapped[int] = mapped_column(Integer, nullable=False)
    page_title: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    generated_summary: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    fetch_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'pending'"),
    )
    warnings: Mapped[list[object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
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

    note: Mapped[Note] = relationship(back_populates="link_processing_results")
    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="link_processing_results")
