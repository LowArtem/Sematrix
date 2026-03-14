from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_paddle_ocr_client_wraps_local_paddleocr_runtime() -> None:
    ocr_source = (BACKEND_APP / "infra" / "ocr.py").read_text(encoding="utf-8")

    assert "class PaddleOcrClient:" in ocr_source
    assert "from paddleocr import PaddleOCR" in ocr_source
    assert "raw_result = self._ocr_engine.ocr(str(image_path), cls=True)" in ocr_source
    assert "return \"\\n\".join(lines)" in ocr_source


def test_process_ocr_reads_snapshot_assets_and_persists_per_asset_results() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert "def list_snapshot_assets(" in pipeline_source
    assert "select(Asset.id, Asset.storage_key)" in pipeline_source
    assert "assets = self._runtime_repository.list_snapshot_assets(" in pipeline_source
    assert "image_path = get_asset_path(asset.storage_key)" in pipeline_source
    assert "ocr_text = self._ocr_client.extract_text(image_path=image_path)" in pipeline_source
    assert "self._runtime_repository.store_asset_ocr_result(" in pipeline_source
    assert 'ocr_status = "done"' in pipeline_source


def test_process_ocr_downgrades_single_asset_failures_to_warnings() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert "except OcrClientError as exc:" in pipeline_source
    assert 'stage="ocr"' in pipeline_source
    assert 'code="ocr_failed"' in pipeline_source
    assert 'ocr_status = "error"' in pipeline_source
    assert 'retryable=False' in pipeline_source
    assert '"warnings_count": warning_count,' in pipeline_source
    assert "ocr_client=PaddleOcrClient()" in pipeline_source
