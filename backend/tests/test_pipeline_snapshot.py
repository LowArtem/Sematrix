from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_pipeline_snapshot_hash_and_repository_are_defined() -> None:
    domain_source = (BACKEND_APP / "domain" / "pipeline.py").read_text(encoding="utf-8")
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")

    assert 'def compute_snapshot_hash(*, asset_ids: list[UUID], link_ids: list[UUID]) -> str:' in domain_source
    assert 'sorted_asset_ids = sorted(str(asset_id) for asset_id in asset_ids)' in domain_source
    assert 'sorted_link_ids = sorted(str(link_id) for link_id in link_ids)' in domain_source
    assert 'return sha256(snapshot_payload.encode("utf-8")).hexdigest()' in domain_source
    assert 'def _create_pipeline_run(' in infra_source
    assert 'self._session.scalars(select(NoteAsset.asset_id).where(NoteAsset.note_id == note_id)).all()' in infra_source
    assert 'self._session.scalars(select(NoteLink.id).where(NoteLink.note_id == note_id)).all()' in infra_source
    assert 'snapshot_hash=compute_snapshot_hash(' in infra_source
    assert 'PipelineRun(' in infra_source
    assert 'request_id=request_id,' in infra_source
