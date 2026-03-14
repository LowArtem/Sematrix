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


def downgrade() -> None:
    op.drop_table("note_tags")
    op.drop_table("tags")
    op.drop_table("notes")
    op.drop_table("folders")
    sa.Enum("Draft", "Processing", "Ready", "Error", name="note_status").drop(
        op.get_bind(),
        checkfirst=True,
    )
    op.execute("DROP EXTENSION IF EXISTS vector")
