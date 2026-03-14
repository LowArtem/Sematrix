from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_api_error_files_exist() -> None:
    expected_paths = [
        BACKEND_APP / "api" / "dto.py",
        BACKEND_APP / "api" / "errors.py",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_error_handlers_are_registered_from_main() -> None:
    main_source = (BACKEND_APP / "main.py").read_text(encoding="utf-8")
    errors_source = (BACKEND_APP / "api" / "errors.py").read_text(encoding="utf-8")
    dto_source = (BACKEND_APP / "api" / "dto.py").read_text(encoding="utf-8")

    assert "from app.api.errors import register_exception_handlers" in main_source
    assert "register_exception_handlers(app)" in main_source
    assert "class ApiErrorDto(BaseModel):" in dto_source
    assert "@app.exception_handler(RequestValidationError)" in errors_source
    assert "@app.exception_handler(StarletteHTTPException)" in errors_source
    assert "@app.exception_handler(Exception)" in errors_source
    assert '"validation_error"' in errors_source
    assert '"not_found"' in errors_source
    assert '"conflict"' in errors_source
    assert '"payload_too_large"' in errors_source
    assert '"unsupported_media_type"' in errors_source
    assert '"internal_server_error"' in errors_source
    assert 'details={"errors": _format_validation_details(exc)}' in errors_source
