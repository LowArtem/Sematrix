import importlib.util
import sys
from pathlib import Path
from uuid import uuid4

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
NOTE_CONTENT_MODULE_PATH = BACKEND_ROOT / "app" / "domain" / "note_content.py"


def load_note_content_module():
    sys.path.insert(0, str(BACKEND_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(
            "sematrix_test_note_content",
            NOTE_CONTENT_MODULE_PATH,
        )
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if sys.path and sys.path[0] == str(BACKEND_ROOT):
            sys.path.pop(0)


def test_parse_note_content_extracts_deduplicated_links_from_text_and_marks() -> None:
    module = load_note_content_module()
    asset_id = uuid4()

    parsed = module.parse_note_content(
        {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "See https://Example.com/path?a=2&b=1. and this YouTube video",
                        },
                        {
                            "type": "text",
                            "text": "watch",
                            "marks": [
                                {
                                    "type": "link",
                                    "attrs": {"href": "https://www.youtube.com/watch?v=abc123&t=5"},
                                }
                            ],
                        },
                    ],
                },
                {"type": "image", "attrs": {"assetId": str(asset_id)}},
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "Same URL again",
                            "marks": [
                                {
                                    "type": "link",
                                    "attrs": {"href": "https://example.com/path?b=1&a=2"},
                                }
                            ],
                        }
                    ],
                },
            ],
        }
    )

    assert parsed.content_text_flat == "See https://Example.com/path?a=2&b=1. and this YouTube video watch Same URL again"
    assert parsed.asset_ids == [asset_id]
    assert [link.url for link in parsed.links] == [
        "https://Example.com/path?a=2&b=1",
        "https://www.youtube.com/watch?v=abc123&t=5",
    ]
    assert [link.normalized_url for link in parsed.links] == [
        "https://example.com/path?a=2&b=1",
        "https://www.youtube.com/watch?t=5&v=abc123",
    ]
    assert [link.link_type for link in parsed.links] == ["web", "youtube_video"]


@pytest.mark.parametrize(
    ("url", "expected_type"),
    [
        ("https://youtu.be/demo", "youtube_video"),
        ("https://www.youtube.com/watch?v=demo", "youtube_video"),
        ("https://www.youtube.com/shorts/demo", "youtube_video"),
        ("https://www.youtube.com/channel/demo", "youtube_channel"),
        ("https://www.youtube.com/@sematrix", "youtube_channel"),
        ("https://example.com/notes.md", "text_file"),
        ("https://example.com/files/report.pdf", "other"),
        ("https://example.com/articles/readme", "web"),
    ],
)
def test_classify_note_link_covers_required_link_types(url: str, expected_type: str) -> None:
    module = load_note_content_module()

    normalized_url = module.normalize_note_url(url)

    assert normalized_url is not None
    assert module.classify_note_link(normalized_url) == expected_type


def test_parse_note_content_rejects_invalid_image_asset_ids() -> None:
    module = load_note_content_module()

    with pytest.raises(module.DomainError, match="invalid image assetId"):
        module.parse_note_content(
            {
                "type": "doc",
                "content": [{"type": "image", "attrs": {"assetId": "not-a-uuid"}}],
            }
        )
