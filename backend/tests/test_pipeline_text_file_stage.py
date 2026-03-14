from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def _load_ollama_module():
    import importlib.util
    import sys

    module_name = "test_ollama_text_file_runtime"
    module_path = BACKEND_APP / "infra" / "ollama.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load ollama module")

    module = importlib.util.module_from_spec(spec)
    sys.modules.pop(module_name, None)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_pipeline_stage_runner_processes_text_file_links() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert 'link.link_type not in {"youtube_video", "youtube_channel", "text_file"}' in pipeline_source
    assert "def _process_text_file_link(" in pipeline_source
    assert "self._link_fetcher.fetch(url=url)" in pipeline_source
    assert "len(response.body) > self._max_text_file_bytes" in pipeline_source
    assert 'code="text_file_summary_failed"' in pipeline_source
    assert '"source": "text_file"' in pipeline_source
    assert "generate_text_file_summary(" in pipeline_source


def test_pipeline_stage_runner_factory_wires_text_file_size_limit() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert "max_text_file_bytes=settings.max_text_file_mb * 1024 * 1024" in pipeline_source


def test_ollama_client_supports_non_thinking_text_file_summaries() -> None:
    ollama_source = (BACKEND_APP / "infra" / "ollama.py").read_text(encoding="utf-8")

    assert "def generate_text_file_summary(" in ollama_source
    assert '"/no_think\\n"' in ollama_source
    assert '"Write a short plain-text summary for a downloaded text file. "' in ollama_source


def test_generate_text_file_summary_posts_non_thinking_prompt() -> None:
    ollama_module = _load_ollama_module()
    requested_payloads: list[tuple[str, bytes, int]] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"response": "A concise summary."}'

    def fake_urlopen(http_request, timeout):
        requested_payloads.append((http_request.full_url, http_request.data, timeout))
        return FakeResponse()

    original_urlopen = ollama_module.request.urlopen
    ollama_module.request.urlopen = fake_urlopen
    try:
        client = ollama_module.OllamaClient(
            base_url="http://ollama.local",
            llm_model="qwen3.5:9b",
            embed_model="bge-m3",
            vision_model="qwen3.5:9b",
            timeout_sec=9,
        )
        summary = client.generate_text_file_summary(
            source_name="notes.md",
            content_text="Sematrix keeps note processing local and snapshot-safe.",
        )
    finally:
        ollama_module.request.urlopen = original_urlopen

    assert summary == "A concise summary."
    assert len(requested_payloads) == 1
    requested_url, raw_body, timeout = requested_payloads[0]
    assert requested_url == "http://ollama.local/api/generate"
    assert timeout == 9
    decoded_body = raw_body.decode("utf-8")
    assert '"model": "qwen3.5:9b"' in decoded_body
    assert "/no_think\\n" in decoded_body
    assert "Source: notes.md" in decoded_body
