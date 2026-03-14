from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_pipeline_stage_runner_processes_youtube_video_links_via_api_client() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert "class SnapshotLinkRecord:" in pipeline_source
    assert "def list_snapshot_links(" in pipeline_source
    assert "def store_link_result(" in pipeline_source
    assert 'if link.link_type not in {"youtube_video", "youtube_channel"}:' in pipeline_source
    assert 'metadata = self._youtube_client.fetch_video_metadata(url=link.url)' in pipeline_source
    assert 'content_type = "application/vnd.youtube.video+json"' in pipeline_source
    assert 'metadata_json = metadata.to_metadata_dict()' in pipeline_source
    assert 'generated_summary = metadata.build_summary()' in pipeline_source
    assert 'code=f"{link.link_type}_fetch_failed"' in pipeline_source


def test_pipeline_stage_runner_factory_wires_the_youtube_client() -> None:
    pipeline_source = (BACKEND_APP / "infra" / "pipeline.py").read_text(encoding="utf-8")

    assert "from app.infra.youtube import YouTubeDataApiClient, YouTubeDataApiClientError" in pipeline_source
    assert "youtube_client=YouTubeDataApiClient(" in pipeline_source
    assert "api_key=settings.youtube_api_key," in pipeline_source
    assert "timeout_sec=settings.link_fetch_timeout_sec," in pipeline_source
