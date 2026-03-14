from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_worker_tasks_define_fixed_retry_policy() -> None:
    worker_source = (BACKEND_APP / "workers" / "tasks.py").read_text(encoding="utf-8")

    assert 'NETWORK_TASK_RETRY_KWARGS = {"max_retries": 2}' in worker_source
    assert 'NETWORK_TASK_RETRY_BACKOFF = True' in worker_source
    assert 'NETWORK_TASK_RETRY_JITTER = False' in worker_source
    assert 'ENRICHMENT_TASK_RETRY_KWARGS = {"max_retries": 1}' in worker_source
    assert 'name="sematrix.process_links"' in worker_source
    assert 'autoretry_for=NETWORK_TASK_AUTORETRY_FOR' in worker_source
    assert 'retry_kwargs=NETWORK_TASK_RETRY_KWARGS' in worker_source
    assert 'retry_backoff=NETWORK_TASK_RETRY_BACKOFF' in worker_source
    assert 'retry_jitter=NETWORK_TASK_RETRY_JITTER' in worker_source
    assert 'name="sematrix.process_ocr"' in worker_source
    assert 'autoretry_for=ENRICHMENT_TASK_AUTORETRY_FOR' in worker_source
    assert 'retry_kwargs=ENRICHMENT_TASK_RETRY_KWARGS' in worker_source
    assert 'name="sematrix.process_image_caption"' in worker_source


def test_pipeline_failure_handler_marks_exhausted_noncritical_stage_failures_retryable() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert 'callback_kwargs.get(' in pipeline_source
    assert 'is_noncritical_pipeline_stage(failed_task_name)' in pipeline_source
    assert 'retryable=bool(' in pipeline_source
