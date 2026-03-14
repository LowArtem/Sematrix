from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_ollama_client_supports_non_thinking_image_caption_requests() -> None:
    ollama_source = (BACKEND_APP / "infra" / "ollama.py").read_text(encoding="utf-8")

    assert "def generate_image_caption(" in ollama_source
    assert '"model": self._vision_model,' in ollama_source
    assert '"images": [encoded_image],' in ollama_source
    assert '"/no_think\\n"' in ollama_source
    assert "base64.b64encode(image_path.read_bytes()).decode(\"ascii\")" in ollama_source


def test_process_image_caption_reads_snapshot_assets_and_persists_per_asset_results() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert "def store_asset_caption_result(" in pipeline_source
    assert "assets = self._runtime_repository.list_snapshot_assets(" in pipeline_source
    assert 'stage_name="process_image_caption"' in pipeline_source
    assert "image_path = get_asset_path(asset.storage_key)" in pipeline_source
    assert "caption_text = self._ollama_client.generate_image_caption(image_path=image_path)" in pipeline_source
    assert "self._runtime_repository.store_asset_caption_result(" in pipeline_source
    assert 'caption_status = "done"' in pipeline_source


def test_process_image_caption_downgrades_single_asset_failures_to_warnings() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert "except OllamaClientError as exc:" in pipeline_source
    assert 'stage="image_caption"' in pipeline_source
    assert 'code="image_caption_failed"' in pipeline_source
    assert 'caption_status = "error"' in pipeline_source
    assert 'retryable=False' in pipeline_source
    assert '"warnings_count": warning_count,' in pipeline_source
    assert "vision_model=settings.vision_model" in pipeline_source
