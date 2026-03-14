from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_backend_foundation_files_exist() -> None:
    expected_paths = [
        BACKEND_APP / "api" / "dependencies.py",
        BACKEND_APP / "api" / "router.py",
        BACKEND_APP / "api" / "routes" / "system.py",
        BACKEND_APP / "domain" / "system.py",
        BACKEND_APP / "infra" / "system.py",
        BACKEND_APP / "workers" / "tasks.py",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_fastapi_entrypoint_uses_router_wiring() -> None:
    main_source = (BACKEND_APP / "main.py").read_text(encoding="utf-8")
    router_source = (BACKEND_APP / "api" / "router.py").read_text(encoding="utf-8")
    dependency_source = (BACKEND_APP / "api" / "dependencies.py").read_text(encoding="utf-8")

    assert "def create_app() -> FastAPI:" in main_source
    assert "app = create_app()" in main_source
    assert "app.include_router(public_router)" in main_source
    assert "app.include_router(api_router)" in main_source
    assert 'api_router = APIRouter(prefix="/api")' in router_source
    assert "def get_system_status_service() -> SystemStatusService:" in dependency_source
    assert "RuntimeMetadataRepository" in dependency_source


def test_workers_delegate_to_domain_services() -> None:
    worker_task_source = (BACKEND_APP / "workers" / "tasks.py").read_text(encoding="utf-8")
    celery_source = (BACKEND_APP / "workers" / "celery_app.py").read_text(encoding="utf-8")
    domain_source = (BACKEND_APP / "domain" / "system.py").read_text(encoding="utf-8")

    assert "from app.domain.system import WorkerHeartbeatService" in worker_task_source
    assert "service = WorkerHeartbeatService()" in worker_task_source
    assert "return service.ping()" in worker_task_source
    assert 'include=["app.workers.tasks"]' in celery_source
    assert "class SystemStatusService:" in domain_source
    assert "class WorkerHeartbeatService:" in domain_source
