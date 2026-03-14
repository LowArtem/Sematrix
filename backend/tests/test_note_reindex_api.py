from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_note_reindex_route_uses_async_contract() -> None:
    route_source = (BACKEND_APP / "api" / "routes" / "notes.py").read_text(encoding="utf-8")

    assert '@api_notes_router.post(' in route_source
    assert '"/{note_id}/reindex"' in route_source
    assert 'response_model=AsyncAcceptedDto' in route_source
    assert 'status_code=status.HTTP_202_ACCEPTED' in route_source
    assert 'message="Note reindex accepted and processing started"' in route_source


def test_note_reindex_service_dispatches_pipeline_with_request_context() -> None:
    domain_source = (BACKEND_APP / "domain" / "notes.py").read_text(encoding="utf-8")

    assert 'def reindex_note(self, note_id: UUID, *, request_id: str | None) -> NoteResult:' in domain_source
    assert 'reindex_result = self._note_repository.reindex_note(note_id, request_id=request_id)' in domain_source
    assert '"event": "note_processing_started"' in domain_source
    assert 'self._pipeline_dispatcher.start_pipeline(' in domain_source
    assert 'request_id=request_id,' in domain_source


def test_note_reindex_repository_increments_version_and_resets_runtime_state() -> None:
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")

    assert 'def reindex_note(self, note_id: UUID, *, request_id: str | None) -> ReindexNoteRecord:' in infra_source
    assert 'note.index_version += 1' in infra_source
    assert 'note.status = "Processing"' in infra_source
    assert 'note.processing_error = None' in infra_source
    assert 'note.has_warnings = False' in infra_source
    assert 'note.warnings_count = 0' in infra_source
    assert 'note.processing_warnings = []' in infra_source
    assert 'pipeline_run = self._create_pipeline_run(' in infra_source
