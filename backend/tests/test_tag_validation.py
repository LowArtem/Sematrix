from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_tag_normalization_module_exists() -> None:
    expected_paths = [
        BACKEND_APP / "domain" / "tags.py",
        BACKEND_APP / "api" / "dto.py",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_tag_rules_are_centralized_and_reused_by_note_save_dto() -> None:
    dto_source = (BACKEND_APP / "api" / "dto.py").read_text(encoding="utf-8")
    domain_source = (BACKEND_APP / "domain" / "tags.py").read_text(encoding="utf-8")

    assert "from app.domain.tags import normalize_tag_names" in dto_source
    assert '@field_validator("tags")' in dto_source
    assert "return normalize_tag_names(value)" in dto_source
    assert 'TAG_NAME_PATTERN = re.compile(r"^[0-9A-Za-zА-Яа-яЁё_]+$")' in domain_source
    assert 'normalized = value.strip().lower()' in domain_source
    assert 'raise ValueError("Tag name cannot contain spaces")' in domain_source
    assert 'Tag name may contain only Latin/Cyrillic letters, digits, and underscore' in domain_source
    assert "if normalized in seen:" in domain_source
