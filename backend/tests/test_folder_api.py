from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_folder_api_files_exist() -> None:
    expected_paths = [
        BACKEND_APP / "api" / "routes" / "folders.py",
        BACKEND_APP / "domain" / "folders.py",
        BACKEND_APP / "domain" / "errors.py",
        BACKEND_APP / "infra" / "folders.py",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_folder_routes_are_registered() -> None:
    router_source = (BACKEND_APP / "api" / "router.py").read_text(encoding="utf-8")
    route_source = (BACKEND_APP / "api" / "routes" / "folders.py").read_text(encoding="utf-8")
    dependency_source = (BACKEND_APP / "api" / "dependencies.py").read_text(encoding="utf-8")
    domain_source = (BACKEND_APP / "domain" / "folders.py").read_text(encoding="utf-8")
    infra_source = (BACKEND_APP / "infra" / "folders.py").read_text(encoding="utf-8")
    error_source = (BACKEND_APP / "api" / "errors.py").read_text(encoding="utf-8")

    assert "from app.api.routes.folders import api_folders_router" in router_source
    assert "api_router.include_router(api_folders_router)" in router_source
    assert 'api_folders_router = APIRouter(prefix="/folders", tags=["folders"])' in route_source
    assert '@api_folders_router.get("", response_model=list[FolderDto])' in route_source
    assert '@api_folders_router.post("", response_model=FolderDto, status_code=status.HTTP_201_CREATED)' in route_source
    assert '@api_folders_router.patch("/{folder_id}", response_model=FolderDto)' in route_source
    assert '@api_folders_router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)' in route_source
    assert "def get_db_session() -> Iterator[Session]:" in dependency_source
    assert "def get_folder_service(session: Session = Depends(get_db_session)) -> FolderService:" in dependency_source
    assert "class FolderService:" in domain_source
    assert "class SqlAlchemyFolderRepository:" in infra_source
    assert "@app.exception_handler(DomainError)" in error_source


def test_folder_request_dtos_trim_and_validate_names() -> None:
    dto_source = (BACKEND_APP / "api" / "dto.py").read_text(encoding="utf-8")

    assert 'name: str = Field(min_length=1, max_length=255)' in dto_source
    assert '@field_validator("name")' in dto_source
    assert 'raise ValueError("Folder name cannot be empty")' in dto_source
    assert 'normalized = value.strip()' in dto_source
