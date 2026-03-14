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
