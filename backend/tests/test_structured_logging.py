from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_structured_logging_files_exist() -> None:
    expected_paths = [
        BACKEND_APP / "api" / "middleware.py",
        BACKEND_APP / "core" / "logging.py",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_fastapi_and_celery_wire_structured_logging() -> None:
    main_source = (BACKEND_APP / "main.py").read_text(encoding="utf-8")
    middleware_source = (BACKEND_APP / "api" / "middleware.py").read_text(encoding="utf-8")
    logging_source = (BACKEND_APP / "core" / "logging.py").read_text(encoding="utf-8")
    celery_source = (BACKEND_APP / "workers" / "celery_app.py").read_text(encoding="utf-8")
    tasks_source = (BACKEND_APP / "workers" / "tasks.py").read_text(encoding="utf-8")

    assert "configure_logging()" in main_source
    assert "register_request_context_middleware(app)" in main_source
    assert 'request.headers.get("X-Request-Id")' in middleware_source
    assert 'response.headers["X-Request-Id"] = request_id' in middleware_source
    assert '"event": "api_request_started"' in middleware_source
    assert '"event": "api_request_finished"' in middleware_source
    assert 'contextvars.ContextVar("request_id"' in logging_source
    assert 'contextvars.ContextVar("task_id"' in logging_source
    assert '"request_id"' in logging_source
    assert '"task_id"' in logging_source
    assert '"pipeline_run_id"' in logging_source
    assert '"started_at"' in logging_source
    assert 'worker_hijack_root_logger=False' in celery_source
    assert '@task_prerun.connect' in celery_source
    assert '@task_postrun.connect' in celery_source
    assert '"event": "task_started"' in celery_source
    assert '"event": "task_finished"' in celery_source
    assert '@celery_app.task(bind=True, name="sematrix.ping")' in tasks_source
    assert '"event": "worker_heartbeat_requested"' in tasks_source
