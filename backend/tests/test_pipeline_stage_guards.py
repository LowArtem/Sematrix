from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_pipeline_stage_runner_validates_runtime_state_and_snapshot_integrity() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert 'class PipelineStageRuntimeState:' in pipeline_source
    assert 'def get_stage_runtime_state(' in pipeline_source
    assert 'pipeline_run = self._session.get(PipelineRun, pipeline_run_id)' in pipeline_source
    assert 'compute_snapshot_hash(' in pipeline_source
    assert 'if runtime_state.current_index_version != index_version:' in pipeline_source
    assert 'if runtime_state.pipeline_run_note_id != note_id or runtime_state.pipeline_run_index_version != index_version:' in pipeline_source
    assert 'skipped_reason="stale_version"' in pipeline_source
    assert 'skipped_reason="snapshot_mismatch"' in pipeline_source
    assert 'skipped_reason="invalid_snapshot_hash"' in pipeline_source


def test_pipeline_stage_runner_uses_snapshot_scoped_queries_and_not_in_snapshot_guard() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert 'select(NoteAsset.asset_id).where(' in pipeline_source
    assert 'NoteAsset.asset_id.in_(snapshot_asset_ids)' in pipeline_source
    assert 'select(NoteLink.id).where(' in pipeline_source
    assert 'NoteLink.id.in_(snapshot_link_ids)' in pipeline_source
    assert 'for target_id in snapshot_target_ids:' in pipeline_source
    assert 'def _filter_snapshot_target_ids(' in pipeline_source
    assert 'skipped_reason="not_in_snapshot"' in pipeline_source
    assert 'skipped_reason="missing_target"' in pipeline_source


def test_worker_stage_tasks_delegate_to_guarded_stage_runner_with_small_payloads() -> None:
    worker_source = (BACKEND_APP / "workers" / "tasks.py").read_text(encoding="utf-8")

    assert 'build_pipeline_stage_runner(session=session)' in worker_source
    assert 'pipeline_run_id=UUID(pipeline_run_id),' in worker_source
    assert '"duration_ms": int((perf_counter() - started_at) * 1000),' in worker_source
    assert 'content_json' not in worker_source
    assert 'ocr_text' not in worker_source
    assert 'embedding' not in worker_source
