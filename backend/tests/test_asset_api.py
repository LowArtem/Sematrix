from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_asset_api_files_exist() -> None:
    expected_paths = [
        BACKEND_APP / "api" / "routes" / "assets.py",
        BACKEND_APP / "domain" / "assets.py",
        BACKEND_APP / "infra" / "assets.py",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_asset_routes_are_registered() -> None:
    router_source = (BACKEND_APP / "api" / "router.py").read_text(encoding="utf-8")
    route_source = (BACKEND_APP / "api" / "routes" / "assets.py").read_text(encoding="utf-8")
    dependency_source = (BACKEND_APP / "api" / "dependencies.py").read_text(encoding="utf-8")
    domain_source = (BACKEND_APP / "domain" / "assets.py").read_text(encoding="utf-8")
    infra_source = (BACKEND_APP / "infra" / "assets.py").read_text(encoding="utf-8")

    assert "from app.api.routes.assets import api_assets_router" in router_source
    assert "api_router.include_router(api_assets_router)" in router_source
    assert 'api_assets_router = APIRouter(prefix="/assets", tags=["assets"])' in route_source
    assert '@api_assets_router.post("/image", response_model=AssetDto, status_code=status.HTTP_201_CREATED)' in route_source
    assert '@api_assets_router.get("/{asset_id}")' in route_source
    assert "def get_asset_service(session: Session = Depends(get_db_session)) -> AssetService:" in dependency_source
    assert "class AssetService:" in domain_source
    assert "class SqlAlchemyAssetRepository:" in infra_source


def test_asset_upload_validates_type_size_and_note_binding() -> None:
    domain_source = (BACKEND_APP / "domain" / "assets.py").read_text(encoding="utf-8")
    infra_source = (BACKEND_APP / "infra" / "assets.py").read_text(encoding="utf-8")
    requirements_source = (REPO_ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")

    assert 'raise BadRequestError("note_id is required")' in domain_source
    assert '"image/png"' in domain_source
    assert '"image/jpeg"' in domain_source
    assert '"image/webp"' in domain_source
    assert 'raise UnsupportedMediaTypeError("Only PNG, JPEG, and WebP images are supported")' in domain_source
    assert 'raise PayloadTooLargeError("Image file exceeds MAX_IMAGE_MB")' in domain_source
    assert 'self._session.add(NoteAsset(note_id=note.id, asset_id=asset.id))' in infra_source
    assert 'asset_path.write_bytes(content)' in infra_source
    assert 'asset_path.unlink(missing_ok=True)' in infra_source
    assert "python-multipart==0.0.20" in requirements_source


def test_asset_download_uses_backend_content_type() -> None:
    route_source = (BACKEND_APP / "api" / "routes" / "assets.py").read_text(encoding="utf-8")
    infra_source = (BACKEND_APP / "infra" / "assets.py").read_text(encoding="utf-8")

    assert "return FileResponse(" in route_source
    assert "media_type=asset_file.mime_type" in route_source
    assert 'url=f"/api/assets/{asset.id}"' in (BACKEND_APP / "domain" / "assets.py").read_text(encoding="utf-8")
    assert 'raise NotFoundError("Asset not found")' in infra_source
