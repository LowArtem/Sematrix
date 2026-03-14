from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_note_delete_route_is_registered() -> None:
    route_source = (BACKEND_APP / "api" / "routes" / "notes.py").read_text(encoding="utf-8")
    domain_source = (BACKEND_APP / "domain" / "notes.py").read_text(encoding="utf-8")
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")

    assert '@api_notes_router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)' in route_source
    assert "service.delete_note(note_id)" in route_source
    assert "return Response(status_code=status.HTTP_204_NO_CONTENT)" in route_source
    assert "def delete_note(self, note_id: UUID) -> None:" in domain_source
    assert "def delete_note(self, note_id: UUID) -> None: ..." in infra_source


def test_note_delete_repository_cleans_orphaned_assets() -> None:
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")
    assets_source = (BACKEND_APP / "infra" / "assets.py").read_text(encoding="utf-8")

    assert "candidate_assets = list(note.assets)" in infra_source
    assert "self._session.delete(note)" in infra_source
    assert "self._session.flush()" in infra_source
    assert "select(NoteAsset.asset_id).where(NoteAsset.asset_id.in_(candidate_asset_ids))" in infra_source
    assert "self._session.delete(asset)" in infra_source
    assert "get_asset_path(storage_key).unlink(missing_ok=True)" in infra_source
    assert 'CONTAINER_ASSETS_ROOT = Path("/data/assets")' in assets_source
    assert 'return Path(__file__).resolve().parents[3] / "data" / "assets"' in assets_source
