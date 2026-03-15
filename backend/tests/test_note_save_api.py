from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_note_save_route_exposes_draft_and_processing_contracts() -> None:
    route_source = (BACKEND_APP / "api" / "routes" / "notes.py").read_text(encoding="utf-8")

    assert '@api_notes_router.patch(' in route_source
    assert 'response_model=NoteDetailDto | AsyncAcceptedDto' in route_source
    assert 'payload: NoteSaveRequestDto' in route_source
    assert 'response.status_code = status.HTTP_202_ACCEPTED' in route_source
    assert 'message="Note save accepted and processing started"' in route_source
    assert 'response.status_code = status.HTTP_200_OK' in route_source


def test_note_save_service_parses_content_and_dispatches_pipeline() -> None:
    domain_source = (BACKEND_APP / "domain" / "notes.py").read_text(encoding="utf-8")
    lifecycle_source = (BACKEND_APP / "domain" / "note_lifecycle.py").read_text(encoding="utf-8")
    parsing_source = (BACKEND_APP / "domain" / "note_content.py").read_text(encoding="utf-8")
    pipeline_domain_source = (BACKEND_APP / "domain" / "pipeline.py").read_text(encoding="utf-8")
    dependency_source = (BACKEND_APP / "api" / "dependencies.py").read_text(encoding="utf-8")
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert 'parsed_content = parse_note_content(content_json)' in domain_source
    assert 'should_start_processing = has_meaningful_content(' in domain_source
    assert 'search_text = build_search_text(' in domain_source
    assert 'search_text=search_text,' in domain_source
    assert 'should_start_processing=should_start_processing' in domain_source
    assert '"event": "note_processing_started"' in domain_source
    assert 'pipeline_run = save_result.pipeline_run' in domain_source
    assert '"started_at": pipeline_run.started_at.isoformat()' in domain_source
    assert 'self._pipeline_dispatcher.start_pipeline(' in domain_source
    assert 'class DraftResetState:' in lifecycle_source
    assert 'def build_draft_reset_state() -> DraftResetState:' in lifecycle_source
    assert 'return bool(content_text_flat.strip() or asset_count > 0 or link_count > 0)' in lifecycle_source
    assert 'URL_PATTERN = re.compile(r"https?://[^\\s<>()]+", re.IGNORECASE)' in parsing_source
    assert 'def build_search_text(' in pipeline_domain_source
    assert 'if node_type == "image" and isinstance(attrs.get("assetId"), str):' in parsing_source
    assert 'if not isinstance(mark, dict) or mark.get("type") != "link":' in parsing_source
    assert 'pipeline_dispatcher=CeleryPipelineDispatcher(),' in dependency_source
    assert 'celery_app.send_task(' in pipeline_source
    assert '"sematrix.start_pipeline"' in pipeline_source


def test_note_save_repository_syncs_links_assets_and_processing_state() -> None:
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")
    worker_source = (BACKEND_APP / "workers" / "tasks.py").read_text(encoding="utf-8")

    assert 'def save_note(' in infra_source
    assert 'note.content_text_flat = content_text_flat' in infra_source
    assert 'note.assets = assets' in infra_source
    assert 'self._sync_note_links(note=note, links=links)' in infra_source
    assert 'should_start_processing: bool' in infra_source
    assert 'request_id: str | None,' in infra_source
    assert 'self._session.flush()' in infra_source
    assert 'if should_start_processing:' in infra_source
    assert 'note.index_version += 1' in infra_source
    assert 'note.status = "Processing"' in infra_source
    assert 'note.search_text = search_text' in infra_source
    assert 'pipeline_run = self._create_pipeline_run(' in infra_source
    assert 'snapshot_link_ids = sorted(' in infra_source
    assert 'snapshot_hash=compute_snapshot_hash(' in infra_source
    assert 'draft_reset_state = build_draft_reset_state()' in infra_source
    assert 'note.status = "Draft"' in infra_source
    assert 'note.summary = draft_reset_state.summary' in infra_source
    assert 'note.search_text = draft_reset_state.search_text' in infra_source
    assert 'note.embedding = draft_reset_state.embedding' in infra_source
    assert 'note.processing_error = draft_reset_state.processing_error' in infra_source
    assert 'note.has_warnings = draft_reset_state.has_warnings' in infra_source
    assert 'note.warnings_count = draft_reset_state.warnings_count' in infra_source
    assert 'note.processing_warnings = draft_reset_state.processing_warnings' in infra_source
    assert 'name="sematrix.start_pipeline"' in worker_source
    assert '"pipeline_entrypoint_requested"' in worker_source
    assert 'name="sematrix.finalize_pipeline"' in worker_source
    assert 'name="sematrix.pipeline_failed"' in worker_source
