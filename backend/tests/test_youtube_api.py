from pathlib import Path
from urllib import parse


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def _load_youtube_module():
    import importlib.util
    import sys

    module_name = "test_youtube_runtime"
    module_path = BACKEND_APP / "infra" / "youtube.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load youtube module")

    module = importlib.util.module_from_spec(spec)
    sys.modules.pop(module_name, None)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_youtube_source_declares_video_metadata_client_and_fields() -> None:
    youtube_source = (BACKEND_APP / "infra" / "youtube.py").read_text(encoding="utf-8")

    assert "class YouTubeDataApiClient:" in youtube_source
    assert "class YouTubeVideoMetadata:" in youtube_source
    assert "class YouTubeChannelMetadata:" in youtube_source
    assert '"part": "snippet,contentDetails,statistics"' in youtube_source
    assert '"video_id": self.video_id,' in youtube_source
    assert '"channel_id": self.channel_id,' in youtube_source
    assert '"channel_title": self.channel_title,' in youtube_source
    assert '"default_language": self.default_language,' in youtube_source
    assert '"default_audio_language": self.default_audio_language,' in youtube_source
    assert '"live_broadcast_content": self.live_broadcast_content,' in youtube_source
    assert '"statistics": dict(self.statistics),' in youtube_source
    assert "def fetch_channel_metadata" in youtube_source
    assert '"published_at": self.published_at,' in youtube_source
    assert '"custom_url": self.custom_url,' in youtube_source


def test_extract_youtube_video_id_supports_required_url_shapes() -> None:
    youtube_module = _load_youtube_module()

    assert youtube_module.extract_youtube_video_id("https://youtu.be/demo123") == "demo123"
    assert youtube_module.extract_youtube_video_id("https://www.youtube.com/watch?v=demo123&t=5") == "demo123"
    assert youtube_module.extract_youtube_video_id("https://www.youtube.com/shorts/demo123") == "demo123"
    assert youtube_module.extract_youtube_video_id("https://www.youtube.com/embed/demo123") == "demo123"
    assert youtube_module.extract_youtube_video_id("https://www.youtube.com/@sematrix") is None


def test_extract_youtube_channel_lookup_supports_required_url_shapes() -> None:
    youtube_module = _load_youtube_module()

    channel_lookup = youtube_module.extract_youtube_channel_lookup("https://www.youtube.com/channel/UC123demo")
    assert channel_lookup.query_param == "id"
    assert channel_lookup.query_value == "UC123demo"

    handle_lookup = youtube_module.extract_youtube_channel_lookup("https://www.youtube.com/@sematrix")
    assert handle_lookup.query_param == "forHandle"
    assert handle_lookup.query_value == "sematrix"

    username_lookup = youtube_module.extract_youtube_channel_lookup("https://www.youtube.com/user/SematrixDocs")
    assert username_lookup.query_param == "forUsername"
    assert username_lookup.query_value == "SematrixDocs"


def test_fetch_video_metadata_requires_api_key() -> None:
    youtube_module = _load_youtube_module()
    client = youtube_module.YouTubeDataApiClient(api_key="")

    try:
        client.fetch_video_metadata(url="https://www.youtube.com/watch?v=demo123")
    except youtube_module.YouTubeDataApiClientError as exc:
        assert exc.retryable is False
        assert "YOUTUBE_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing API key to be rejected")


def test_youtube_video_metadata_builds_index_text_and_summary() -> None:
    youtube_module = _load_youtube_module()
    metadata = youtube_module.YouTubeVideoMetadata(
        video_id="demo123",
        channel_id="channel456",
        channel_title="Sematrix Channel",
        title="Pipeline walkthrough",
        description="How the indexing pipeline works.",
        published_at="2026-03-15T12:00:00Z",
        duration="PT12M34S",
        tags=["sematrix", "pipeline"],
        thumbnails={"default": {"url": "https://example.com/thumb.jpg"}},
        default_language="en",
        default_audio_language="en",
        category_id="27",
        live_broadcast_content="none",
        statistics={"viewCount": "42", "likeCount": "7"},
    )

    index_text = metadata.build_index_text()
    summary = metadata.build_summary()

    assert "Pipeline walkthrough" in index_text
    assert "Sematrix Channel" in index_text
    assert "Duration: PT12M34S" in index_text
    assert "Statistics: viewCount: 42, likeCount: 7" in index_text
    assert summary == 'YouTube video "Pipeline walkthrough" by Sematrix Channel. Duration PT12M34S, published 2026-03-15T12:00:00Z.'


def test_youtube_channel_metadata_builds_index_text_and_summary() -> None:
    youtube_module = _load_youtube_module()
    metadata = youtube_module.YouTubeChannelMetadata(
        channel_id="channel456",
        title="Sematrix Channel",
        description="Local-first notes and indexing demos.",
        published_at="2024-10-02T08:00:00Z",
        thumbnails={"default": {"url": "https://example.com/channel.jpg"}},
        custom_url="@sematrix",
    )

    index_text = metadata.build_index_text()
    summary = metadata.build_summary()

    assert "Sematrix Channel" in index_text
    assert "Local-first notes and indexing demos." in index_text
    assert "Published at: 2024-10-02T08:00:00Z" in index_text
    assert "Custom URL: @sematrix" in index_text
    assert summary == 'YouTube channel "Sematrix Channel". Published 2024-10-02T08:00:00Z.'


def test_fetch_channel_metadata_uses_youtube_data_api_lookup() -> None:
    youtube_module = _load_youtube_module()
    requested_urls: list[str] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return (
                b'{"items": [{"id": "channel456", "snippet": {'
                b'"title": "Sematrix Channel", '
                b'"description": "Local-first notes and indexing demos.", '
                b'"publishedAt": "2024-10-02T08:00:00Z", '
                b'"customUrl": "@sematrix", '
                b'"thumbnails": {"default": {"url": "https://example.com/channel.jpg"}}'
                b'}}]}'
            )

    def fake_urlopen(http_request, timeout):
        requested_urls.append(http_request.full_url)
        assert timeout == 7
        return FakeResponse()

    original_urlopen = youtube_module.request.urlopen
    youtube_module.request.urlopen = fake_urlopen
    try:
        client = youtube_module.YouTubeDataApiClient(api_key="secret-key", timeout_sec=7)
        metadata = client.fetch_channel_metadata(url="https://www.youtube.com/@sematrix")
    finally:
        youtube_module.request.urlopen = original_urlopen

    assert metadata.channel_id == "channel456"
    assert metadata.title == "Sematrix Channel"
    assert metadata.custom_url == "@sematrix"
    assert len(requested_urls) == 1

    parsed_request = parse.urlsplit(requested_urls[0])
    query_params = parse.parse_qs(parsed_request.query)
    assert parsed_request.path.endswith("/channels")
    assert query_params["part"] == ["snippet"]
    assert query_params["forHandle"] == ["sematrix"]
    assert query_params["key"] == ["secret-key"]
