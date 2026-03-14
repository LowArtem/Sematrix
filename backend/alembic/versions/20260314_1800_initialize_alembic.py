"""Initialize Alembic migration workflow.

Revision ID: 20260314_1800
Revises:
Create Date: 2026-03-14 18:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision = "20260314_1800"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    note_status = postgresql.ENUM(
        "Draft",
        "Processing",
        "Ready",
        "Error",
        name="note_status",
        create_type=False,
    )
    note_status.create(op.get_bind(), checkfirst=True)

    pipeline_run_status = postgresql.ENUM(
        "Processing",
        "Ready",
        "Error",
        name="pipeline_run_status",
        create_type=False,
    )
    pipeline_run_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_folders")),
        sa.UniqueConstraint("name", name=op.f("uq_folders_name")),
    )

    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("summary", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "content_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{\"type\": \"doc\", \"content\": []}'::jsonb"),
            nullable=False,
        ),
        sa.Column("content_text_flat", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("status", note_status, server_default=sa.text("'Draft'"), nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("has_warnings", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("warnings_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "processing_warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("index_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("search_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('russian', coalesce(search_text, '')) || to_tsvector('english', coalesce(search_text, ''))",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.ForeignKeyConstraint(
            ["folder_id"],
            ["folders.id"],
            name=op.f("fk_notes_folder_id_folders"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notes")),
    )

    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tags")),
        sa.UniqueConstraint("name", name=op.f("uq_tags_name")),
    )

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_ext", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_assets_storage_key")),
    )

    op.create_table(
        "note_tags",
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["notes.id"],
            name=op.f("fk_note_tags_note_id_notes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name=op.f("fk_note_tags_tag_id_tags"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("note_id", "tag_id", name=op.f("pk_note_tags")),
    )

    op.create_table(
        "note_assets",
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["notes.id"],
            name=op.f("fk_note_assets_note_id_notes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_note_assets_asset_id_assets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("note_id", "asset_id", name=op.f("pk_note_assets")),
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("index_version", sa.Integer(), nullable=False),
        sa.Column(
            "snapshot_asset_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_link_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            pipeline_run_status,
            server_default=sa.text("'Processing'"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "stage_durations_ms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["notes.id"],
            name=op.f("fk_pipeline_runs_note_id_notes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_runs")),
        sa.UniqueConstraint("note_id", "index_version", name=op.f("uq_pipeline_runs_note_id_index_version")),
    )

    op.create_table(
        "asset_processing_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("index_version", sa.Integer(), nullable=False),
        sa.Column("ocr_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("caption_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "ocr_status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "caption_status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_asset_processing_results_asset_id_assets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["notes.id"],
            name=op.f("fk_asset_processing_results_note_id_notes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_runs.id"],
            name=op.f("fk_asset_processing_results_pipeline_run_id_pipeline_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_processing_results")),
        sa.UniqueConstraint(
            "pipeline_run_id",
            "asset_id",
            name=op.f("uq_asset_processing_results_pipeline_run_id_asset_id"),
        ),
    )

    op.create_table(
        "link_processing_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("index_version", sa.Integer(), nullable=False),
        sa.Column("page_title", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("extracted_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("generated_summary", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "fetch_status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["notes.id"],
            name=op.f("fk_link_processing_results_note_id_notes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_runs.id"],
            name=op.f("fk_link_processing_results_pipeline_run_id_pipeline_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_link_processing_results")),
        sa.UniqueConstraint(
            "pipeline_run_id",
            "link_id",
            name=op.f("uq_link_processing_results_pipeline_run_id_link_id"),
        ),
    )

    op.create_index(
        op.f("ix_notes_folder_id_updated_at_id"),
        "notes",
        ["folder_id", "updated_at", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notes_search_tsv"),
        "notes",
        ["search_tsv"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_note_tags_tag_id_note_id"),
        "note_tags",
        ["tag_id", "note_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_note_assets_asset_id_note_id"),
        "note_assets",
        ["asset_id", "note_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_processing_results_note_id_index_version"),
        "asset_processing_results",
        ["note_id", "index_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_link_processing_results_note_id_index_version"),
        "link_processing_results",
        ["note_id", "index_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_link_processing_results_note_id_index_version"), table_name="link_processing_results")
    op.drop_index(op.f("ix_asset_processing_results_note_id_index_version"), table_name="asset_processing_results")
    op.drop_index(op.f("ix_note_assets_asset_id_note_id"), table_name="note_assets")
    op.drop_index(op.f("ix_note_tags_tag_id_note_id"), table_name="note_tags")
    op.drop_index(op.f("ix_notes_search_tsv"), table_name="notes")
    op.drop_index(op.f("ix_notes_folder_id_updated_at_id"), table_name="notes")
    op.drop_table("link_processing_results")
    op.drop_table("asset_processing_results")
    op.drop_table("pipeline_runs")
    op.drop_table("note_assets")
    op.drop_table("note_tags")
    op.drop_table("assets")
    op.drop_table("tags")
    op.drop_table("notes")
    op.drop_table("folders")
    sa.Enum("Processing", "Ready", "Error", name="pipeline_run_status").drop(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("Draft", "Processing", "Ready", "Error", name="note_status").drop(
        op.get_bind(),
        checkfirst=True,
    )
    op.execute("DROP EXTENSION IF EXISTS vector")
