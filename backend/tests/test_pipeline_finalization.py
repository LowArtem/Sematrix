from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_pipeline_finalizer_reads_durable_results_and_builds_search_text() -> None:
    domain_source = (BACKEND_APP / "domain" / "pipeline.py").read_text(encoding="utf-8")
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert 'def build_search_text(' in domain_source
    assert 'parts.append(" ".join(f"#{tag_name}" for tag_name in tag_names))' in domain_source
    assert 'class PipelineFinalizationRuntimeState:' in pipeline_source
    assert 'def get_finalization_runtime_state(' in pipeline_source
    assert 'def list_asset_processing_texts(' in pipeline_source
    assert 'def list_link_processing_texts(' in pipeline_source
    assert 'select(AssetProcessingResult)' in pipeline_source
    assert 'select(LinkProcessingResult, NoteLink.url)' in pipeline_source
    assert 'search_text = build_search_text(' in pipeline_source
    assert 'for text in (result.ocr_text, result.caption_text)' in pipeline_source
    assert 'for text in (result.url, result.page_title, result.extracted_text, result.generated_summary)' in pipeline_source


def test_pipeline_finalizer_validates_embedding_and_marks_note_ready() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")
    worker_source = (BACKEND_APP / "workers" / "tasks.py").read_text(encoding="utf-8")
    logging_source = (BACKEND_APP / "core" / "logging.py").read_text(encoding="utf-8")

    assert 'embedding = self._ollama_client.embed_text(text=search_text)' in pipeline_source
    assert 'if len(embedding) != 1024:' in pipeline_source
    assert 'raise ValueError("Embedding dimensionality must be exactly 1024")' in pipeline_source
    assert 'summary = self._ollama_client.generate_summary(search_text=search_text) if search_text else ""' in pipeline_source
    assert 'note.status = "Ready"' in pipeline_source
    assert 'note.processing_error = None' in pipeline_source
    assert 'pipeline_run.status = "Ready"' in pipeline_source
    assert 'pipeline_run.stage_durations_ms = stage_durations_ms' in pipeline_source
    assert '"event": "note_processing_finished"' in pipeline_source
    assert '"total_duration_ms": total_duration_ms' in pipeline_source
    assert '"stage_durations_ms": stage_durations_ms' in pipeline_source
    assert 'build_pipeline_finalizer(session=session)' in worker_source
    assert '"status"' in logging_source
    assert '"total_duration_ms"' in logging_source
    assert '"stage_durations_ms"' in logging_source


def test_pipeline_finalizer_uses_local_ollama_non_thinking_summary_and_embed_requests() -> None:
    ollama_source = (BACKEND_APP / "infra" / "ollama.py").read_text(encoding="utf-8")

    assert 'class OllamaClient:' in ollama_source
    assert '"/api/generate"' in ollama_source
    assert '"/api/embed"' in ollama_source
    assert '"model": self._llm_model,' in ollama_source
    assert '"model": self._embed_model,' in ollama_source
    assert '"stream": False,' in ollama_source
    assert '"/no_think\\n"' in ollama_source
