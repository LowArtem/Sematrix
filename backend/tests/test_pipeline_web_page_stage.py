from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def _load_ollama_module():
    import importlib.util
    import sys

    module_name = "test_ollama_web_page_runtime"
    module_path = BACKEND_APP / "infra" / "ollama.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load ollama module")

    module = importlib.util.module_from_spec(spec)
    sys.modules.pop(module_name, None)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_pipeline_stage_runner_processes_web_links() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert 'link.link_type not in {"youtube_video", "youtube_channel", "text_file", "web"}' in pipeline_source
    assert "def _process_web_link(" in pipeline_source
    assert "extract_main_text(html=decoded_body)" in pipeline_source
    assert "generate_web_page_summary(" in pipeline_source
    assert 'code="web_page_summary_failed"' in pipeline_source
    assert '"source": "web_page"' in pipeline_source


def test_web_page_extractor_uses_allowed_libraries() -> None:
    extractor_source = (BACKEND_APP / "infra" / "web_pages.py").read_text(encoding="utf-8")
    requirements_source = (REPO_ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")

    assert "import trafilatura" in extractor_source
    assert "from readability import Document" in extractor_source
    assert "def extract_main_text(" in extractor_source
    assert "trafilatura==" in requirements_source
    assert "readability-lxml==" in requirements_source


def test_ollama_client_supports_non_thinking_web_page_summaries() -> None:
    ollama_source = (BACKEND_APP / "infra" / "ollama.py").read_text(encoding="utf-8")

    assert "def generate_web_page_summary(" in ollama_source
    assert '"Write a short plain-text summary for a fetched web page. "' in ollama_source
    assert '"Extracted text:\\n"' in ollama_source


def test_generate_web_page_summary_posts_non_thinking_prompt() -> None:
    ollama_module = _load_ollama_module()
    requested_payloads: list[tuple[str, bytes, int]] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"response": "A concise page summary."}'

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
            timeout_sec=11,
        )
        summary = client.generate_web_page_summary(
            page_title="Sematrix docs",
            page_text="Sematrix keeps search, OCR, and link processing local.",
        )
    finally:
        ollama_module.request.urlopen = original_urlopen

    assert summary == "A concise page summary."
    assert len(requested_payloads) == 1
    requested_url, raw_body, timeout = requested_payloads[0]
    assert requested_url == "http://ollama.local/api/generate"
    assert timeout == 11
    decoded_body = raw_body.decode("utf-8")
    assert '"model": "qwen3.5:9b"' in decoded_body
    assert "/no_think\\n" in decoded_body
    assert "Title: Sematrix docs" in decoded_body
    assert "Extracted text:" in decoded_body
