from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_pipeline_finalizer_preserves_processing_warnings_on_ready_notes() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")
    logging_source = (BACKEND_APP / "core" / "logging.py").read_text(encoding="utf-8")

    assert 'processing_warnings = merge_processing_warnings(' in pipeline_source
    assert 'self._runtime_repository.list_processing_warnings(' in pipeline_source
    assert 'note.processing_warnings = processing_warnings' in pipeline_source
    assert 'note.has_warnings = bool(processing_warnings)' in pipeline_source
    assert 'note.warnings_count = len(processing_warnings)' in pipeline_source
    assert 'logger.warning(' in pipeline_source
    assert '"pipeline_processing_warning"' in pipeline_source
    assert '"warning_code"' in logging_source
    assert '"retryable"' in logging_source


def test_pipeline_failed_classifies_noncritical_stage_failures_and_finalizes() -> None:
    domain_source = (BACKEND_APP / "domain" / "pipeline.py").read_text(encoding="utf-8")
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")
    worker_source = (BACKEND_APP / "workers" / "tasks.py").read_text(encoding="utf-8")

    assert 'def is_noncritical_pipeline_stage(stage_name: str | None) -> bool:' in domain_source
    assert 'class PipelineFailureHandler:' in pipeline_source
    assert 'if is_noncritical_pipeline_stage(failed_task_name):' in pipeline_source
    assert 'self._runtime_repository.store_processing_warning(' in pipeline_source
    assert 'return self._finalizer.finalize_pipeline(' in pipeline_source
    assert 'build_pipeline_failure_handler(session=session).handle_failure(' in worker_source


def test_pipeline_failed_marks_critical_failures_error_and_logs_finish_event() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert 'self._runtime_repository.fail_pipeline_run(' in pipeline_source
    assert 'note.status = "Error"' in pipeline_source
    assert 'pipeline_run.status = "Error"' in pipeline_source
    assert '"status": "Error"' in pipeline_source
    assert '"processing_error": processing_error' in pipeline_source
