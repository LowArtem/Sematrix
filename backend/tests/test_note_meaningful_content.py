import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_MODULE_PATH = REPO_ROOT / "backend" / "app" / "domain" / "note_lifecycle.py"


def load_note_lifecycle_module():
    spec = importlib.util.spec_from_file_location("sematrix_test_note_lifecycle", LIFECYCLE_MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_meaningful_content_requires_text_asset_or_http_link() -> None:
    module = load_note_lifecycle_module()

    assert module.has_meaningful_content(content_text_flat="hello", asset_count=0, link_count=0) is True
    assert module.has_meaningful_content(content_text_flat="   ", asset_count=1, link_count=0) is True
    assert module.has_meaningful_content(content_text_flat="   ", asset_count=0, link_count=1) is True
    assert module.has_meaningful_content(content_text_flat="\n\t  ", asset_count=0, link_count=0) is False
