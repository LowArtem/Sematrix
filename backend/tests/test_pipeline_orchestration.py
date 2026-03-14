from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_pipeline_domain_defines_stage_selection_rules() -> None:
    domain_source = (BACKEND_APP / "domain" / "pipeline.py").read_text(encoding="utf-8")

    assert 'PROCESS_LINKS_TASK = "sematrix.process_links"' in domain_source
    assert 'PROCESS_OCR_TASK = "sematrix.process_ocr"' in domain_source
    assert 'PROCESS_IMAGE_CAPTION_TASK = "sematrix.process_image_caption"' in domain_source
    assert 'def build_pipeline_stages(' in domain_source
    assert 'if snapshot_link_ids and not disable_link_fetch:' in domain_source
    assert 'if snapshot_asset_ids and not disable_ocr:' in domain_source
    assert 'if snapshot_asset_ids and not disable_image_caption:' in domain_source
    assert 'return stages' in domain_source


def test_pipeline_orchestrator_loads_runtime_state_and_dispatches_chords() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert 'class PipelineRuntimeState:' in pipeline_source
    assert 'class SqlAlchemyPipelineRuntimeRepository:' in pipeline_source
    assert 'select(PipelineRun).where(' in pipeline_source
    assert 'current_index_version=note.index_version,' in pipeline_source
    assert 'pipeline_run_id=pipeline_run.id,' in pipeline_source
    assert 'stages = build_pipeline_stages(' in pipeline_source
    assert 'if runtime_state.current_index_version != index_version:' in pipeline_source
    assert 'self._celery.send_task(' in pipeline_source
    assert '"sematrix.finalize_pipeline"' in pipeline_source
    assert 'self._celery.signature(' in pipeline_source
    assert 'finalize_signature.link_error(' in pipeline_source
    assert '"sematrix.pipeline_failed"' in pipeline_source
    assert 'self._chord_factory(header)(finalize_signature)' in pipeline_source


def test_worker_tasks_define_pipeline_entrypoint_stage_and_finalize_names() -> None:
    worker_source = (BACKEND_APP / "workers" / "tasks.py").read_text(encoding="utf-8")

    assert '@celery_app.task(bind=True, name="sematrix.start_pipeline")' in worker_source
    assert 'orchestrator = build_pipeline_orchestrator(session=session)' in worker_source
    assert '@celery_app.task(bind=True, name="sematrix.process_links")' in worker_source
    assert '@celery_app.task(bind=True, name="sematrix.process_ocr")' in worker_source
    assert '@celery_app.task(bind=True, name="sematrix.process_image_caption")' in worker_source
    assert '@celery_app.task(bind=True, name="sematrix.finalize_pipeline")' in worker_source
    assert '@celery_app.task(bind=True, name="sematrix.pipeline_failed")' in worker_source
    assert '"pipeline_finalization_requested"' in worker_source
    assert '"pipeline_failure_requested"' in worker_source
