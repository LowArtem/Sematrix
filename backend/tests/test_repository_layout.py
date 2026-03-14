from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repository_layout_matches_specification() -> None:
    expected_paths = [
        REPO_ROOT / "backend",
        REPO_ROOT / "backend" / "app",
        REPO_ROOT / "backend" / "app" / "api",
        REPO_ROOT / "backend" / "app" / "core",
        REPO_ROOT / "backend" / "app" / "domain",
        REPO_ROOT / "backend" / "app" / "infra",
        REPO_ROOT / "backend" / "app" / "workers",
        REPO_ROOT / "backend" / "alembic",
        REPO_ROOT / "backend" / "tests",
        REPO_ROOT / "frontend",
        REPO_ROOT / "scripts",
        REPO_ROOT / "infra",
        REPO_ROOT / "docker-compose.yml",
        REPO_ROOT / "README.md",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_no_unexpected_top_level_product_directories() -> None:
    allowed_directories = {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        "backend",
        "frontend",
        "scripts",
        "infra",
        "docs",
        "data",
        "ralphex",
    }

    top_level_directories = {
        path.name for path in REPO_ROOT.iterdir() if path.is_dir() and not path.name.startswith("__")
    }

    unexpected = sorted(top_level_directories - allowed_directories)

    assert unexpected == []
