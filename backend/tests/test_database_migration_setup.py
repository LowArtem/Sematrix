from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"


def test_alembic_configuration_exists() -> None:
    assert (BACKEND_ROOT / "alembic.ini").exists()
    assert (BACKEND_ROOT / "alembic" / "env.py").exists()
    assert (BACKEND_ROOT / "alembic" / "script.py.mako").exists()


def test_sqlalchemy_foundation_is_defined_in_backend_code() -> None:
    db_module = (BACKEND_ROOT / "app" / "infra" / "db.py").read_text(encoding="utf-8")

    assert "class Base(DeclarativeBase):" in db_module
    assert "create_engine(get_database_url(), pool_pre_ping=True)" in db_module
    assert "SessionLocal = sessionmaker(" in db_module


def test_initial_alembic_revision_is_present() -> None:
    versions_dir = BACKEND_ROOT / "alembic" / "versions"
    revision_files = sorted(path.name for path in versions_dir.glob("*.py"))

    assert revision_files == ["20260314_1800_initialize_alembic.py"]

    env_py = (BACKEND_ROOT / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "target_metadata = Base.metadata" in env_py
    assert "DATABASE_URL" in env_py


def test_core_schema_models_are_registered() -> None:
    models_module = (BACKEND_ROOT / "app" / "infra" / "models.py").read_text(encoding="utf-8")

    assert "class Folder(Base):" in models_module
    assert "class Note(Base):" in models_module
    assert "class Asset(Base):" in models_module
    assert "class AssetProcessingResult(Base):" in models_module
    assert "class Tag(Base):" in models_module
    assert "class LinkProcessingResult(Base):" in models_module
    assert "class NoteAsset(Base):" in models_module
    assert "class NoteLink(Base):" in models_module
    assert "class NoteTag(Base):" in models_module
    assert "class PipelineRun(Base):" in models_module
    assert 'storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)' in models_module
    assert 'size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)' in models_module
    assert 'Vector(1024)' in models_module
    assert "to_tsvector('russian', coalesce(search_text, ''))" in models_module
    assert "to_tsvector('english', coalesce(search_text, ''))" in models_module
    assert 'Index("ix_notes_folder_id_updated_at_id", "folder_id", "updated_at", "id")' in models_module
    assert 'Index("ix_notes_search_tsv", "search_tsv", postgresql_using="gin")' in models_module
    assert 'Index("ix_note_tags_tag_id_note_id", "tag_id", "note_id")' in models_module
    assert 'Index("ix_note_assets_asset_id_note_id", "asset_id", "note_id")' in models_module
    assert 'snapshot_asset_ids: Mapped[list[uuid.UUID]] = mapped_column(' in models_module
    assert 'stage_durations_ms: Mapped[dict[str, int]] = mapped_column(' in models_module
    assert '__tablename__ = "asset_processing_results"' in models_module
    assert '__tablename__ = "link_processing_results"' in models_module
    assert 'UniqueConstraint("pipeline_run_id", "asset_id")' in models_module
    assert 'UniqueConstraint("pipeline_run_id", "link_id")' in models_module
    assert 'Index("ix_asset_processing_results_note_id_index_version", "note_id", "index_version")' in models_module
    assert 'Index("ix_link_processing_results_note_id_index_version", "note_id", "index_version")' in models_module
    assert 'LINK_TYPE_VALUES = ("youtube_video", "youtube_channel", "web", "text_file", "other")' in models_module
    assert '__table_args__ = (UniqueConstraint("note_id", "normalized_url"),)' in models_module
    assert 'Enum(*LINK_TYPE_VALUES, name="link_type", native_enum=True)' in models_module
    assert 'ForeignKey("note_links.id", ondelete="CASCADE")' in models_module
    assert 'ocr_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("\'pending\'"))' in models_module
    assert 'generated_summary: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("\'\'"))' in models_module


def test_initial_revision_creates_core_schema() -> None:
    revision_module = (
        BACKEND_ROOT / "alembic" / "versions" / "20260314_1800_initialize_alembic.py"
    ).read_text(encoding="utf-8")

    assert 'CREATE EXTENSION IF NOT EXISTS vector' in revision_module
    assert 'op.create_table(\n        "folders"' in revision_module
    assert 'op.create_table(\n        "notes"' in revision_module
    assert 'op.create_table(\n        "tags"' in revision_module
    assert 'op.create_table(\n        "assets"' in revision_module
    assert 'op.create_table(\n        "note_tags"' in revision_module
    assert 'op.create_table(\n        "note_assets"' in revision_module
    assert 'op.create_table(\n        "note_links"' in revision_module
    assert 'op.create_table(\n        "pipeline_runs"' in revision_module
    assert 'op.create_table(\n        "asset_processing_results"' in revision_module
    assert 'op.create_table(\n        "link_processing_results"' in revision_module
    assert 'sa.UniqueConstraint("storage_key", name=op.f("uq_assets_storage_key"))' in revision_module
    assert 'sa.UniqueConstraint(\n            "note_id",\n            "normalized_url",' in revision_module
    assert 'sa.UniqueConstraint("note_id", "index_version", name=op.f("uq_pipeline_runs_note_id_index_version"))' in revision_module
    assert 'sa.UniqueConstraint(\n            "pipeline_run_id",\n            "asset_id",' in revision_module
    assert 'sa.UniqueConstraint(\n            "pipeline_run_id",\n            "link_id",' in revision_module
    assert 'op.create_index(\n        op.f("ix_notes_folder_id_updated_at_id"),' in revision_module
    assert 'op.create_index(\n        op.f("ix_notes_search_tsv"),' in revision_module
    assert 'postgresql_using="gin"' in revision_module
    assert 'op.create_index(\n        op.f("ix_note_tags_tag_id_note_id"),' in revision_module
    assert 'op.create_index(\n        op.f("ix_note_assets_asset_id_note_id"),' in revision_module
    assert 'op.create_index(\n        op.f("ix_asset_processing_results_note_id_index_version"),' in revision_module
    assert 'op.create_index(\n        op.f("ix_link_processing_results_note_id_index_version"),' in revision_module
    assert 'postgresql.ARRAY(postgresql.UUID(as_uuid=True))' in revision_module
    assert 'sa.ForeignKeyConstraint(\n            ["link_id"],\n            ["note_links.id"],' in revision_module
    assert 'sa.Enum(\n        "youtube_video",\n        "youtube_channel",\n        "web",\n        "text_file",\n        "other",\n        name="link_type",' in revision_module
    assert 'sa.Enum("Processing", "Ready", "Error", name="pipeline_run_status")' in revision_module
    assert 'sa.Enum("Draft", "Processing", "Ready", "Error", name="note_status")' in revision_module
