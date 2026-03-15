import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
PIPELINE_DOMAIN_MODULE_PATH = BACKEND_ROOT / "app" / "domain" / "pipeline.py"


def load_pipeline_domain_module():
    sys.path.insert(0, str(BACKEND_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(
            "sematrix_test_pipeline_domain",
            PIPELINE_DOMAIN_MODULE_PATH,
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


def test_build_search_text_aggregates_note_and_enrichment_fields() -> None:
    module = load_pipeline_domain_module()

    search_text = module.build_search_text(
        title="  Search Title  ",
        content_text_flat=" Body text ",
        tag_names=["alpha_tag", "beta"],
        asset_texts=[" OCR text ", "", "Caption text"],
        link_texts=[" https://example.com/page ", "Page title", "Extracted link text", "Generated summary"],
    )

    assert search_text == "\n\n".join(
        [
            "Search Title",
            "Body text",
            "#alpha_tag #beta",
            "OCR text",
            "Caption text",
            "https://example.com/page",
            "Page title",
            "Extracted link text",
            "Generated summary",
        ]
    )


def test_build_search_text_excludes_empty_parts() -> None:
    module = load_pipeline_domain_module()

    search_text = module.build_search_text(
        title=" ",
        content_text_flat="",
        tag_names=[],
        asset_texts=["  "],
        link_texts=["\n"],
    )

    assert search_text == ""
