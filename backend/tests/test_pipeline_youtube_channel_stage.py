from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_pipeline_stage_runner_processes_youtube_channel_links_via_api_client() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert "def _process_youtube_channel_link(" in pipeline_source
    assert "fetch_channel_metadata(url=url)" in pipeline_source
    assert '"application/vnd.youtube.channel+json"' in pipeline_source
    assert 'code="youtube_channel_api_fallback"' in pipeline_source
    assert "_fetch_web_fallback_for_youtube_channel" in pipeline_source


def test_pipeline_stage_runner_factory_wires_link_fetcher_for_channel_fallback() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert "from app.infra.link_fetcher import LinkFetchError, SafeLinkFetcher" in pipeline_source
    assert "link_fetcher=SafeLinkFetcher(" in pipeline_source
    assert "max_response_bytes=settings.max_link_response_mb * 1024 * 1024" in pipeline_source
    assert "max_redirects=settings.link_max_redirects" in pipeline_source
