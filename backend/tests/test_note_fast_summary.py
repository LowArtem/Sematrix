from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_note_save_service_generates_fast_summary_and_title_fallback() -> None:
    domain_source = (BACKEND_APP / "domain" / "notes.py").read_text(encoding="utf-8")

    assert 'class NoteGenerationClient(Protocol):' in domain_source
    assert 'effective_title, title_warnings = self._resolve_title(' in domain_source
    assert 'fast_summary, summary_warnings = self._build_fast_summary(' in domain_source
    assert 'stage="title_generation"' in domain_source
    assert 'code="title_generation_failed"' in domain_source
    assert 'stage="summary_fast"' in domain_source
    assert 'code="summary_fast_failed"' in domain_source
    assert 'def build_title_fallback(content_text_flat: str, *, max_length: int = 120) -> str:' in domain_source
    assert 'return f"{normalized_line[: max_length - 3].rstrip()}..."' in domain_source


def test_note_save_repository_persists_fast_summary_and_pre_finalization_warnings() -> None:
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")
    dependency_source = (BACKEND_APP / "api" / "dependencies.py").read_text(encoding="utf-8")

    assert 'summary: str,' in infra_source
    assert 'processing_warnings: list[dict[str, object]],' in infra_source
    assert 'note.summary = summary' in infra_source
    assert 'note.has_warnings = bool(processing_warnings)' in infra_source
    assert 'note.warnings_count = len(processing_warnings)' in infra_source
    assert 'note.processing_warnings = processing_warnings' in infra_source
    assert 'note_generation_client=OllamaClient(' in dependency_source


def test_ollama_client_supports_non_thinking_fast_summary_and_title_generation() -> None:
    ollama_source = (BACKEND_APP / "infra" / "ollama.py").read_text(encoding="utf-8")

    assert 'def generate_fast_summary(' in ollama_source
    assert 'def generate_title(self, *, content_text_flat: str, tag_names: list[str]) -> str:' in ollama_source
    assert '"/no_think\\n"' in ollama_source
    assert '"Write a short note-card summary in 1-2 concise sentences. "' in ollama_source
    assert '"Generate a short plain-text note title. "' in ollama_source
    assert 'def _generate_text(self, *, prompt: str) -> dict[str, Any]:' in ollama_source
