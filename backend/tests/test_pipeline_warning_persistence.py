from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_pipeline_runtime_repository_can_merge_multiple_note_warnings() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert "def store_processing_warnings(" in pipeline_source
    assert "if not warnings:" in pipeline_source
    assert "return self.store_processing_warnings(" in pipeline_source
    assert "note.processing_warnings = merged_warnings" in pipeline_source
    assert "note.has_warnings = bool(merged_warnings)" in pipeline_source
    assert "note.warnings_count = len(merged_warnings)" in pipeline_source


def test_stage_runner_mirrors_per_object_warnings_onto_note_state() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert "def _store_note_processing_warnings(" in pipeline_source
    assert "self._runtime_repository.store_processing_warnings(" in pipeline_source
    assert pipeline_source.count("self._store_note_processing_warnings(") >= 3
