import importlib.util
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_MODULE_PATH = REPO_ROOT / "backend" / "app" / "core" / "config.py"


def load_config_module():
    spec = importlib.util.spec_from_file_location("sematrix_test_config", CONFIG_MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_config_module_declares_all_required_env_names() -> None:
    config_source = CONFIG_MODULE_PATH.read_text(encoding="utf-8")

    expected_env_names = [
        "APP_ENV",
        "API_HOST",
        "API_PORT",
        "FRONTEND_PORT",
        "DATABASE_URL",
        "REDIS_URL",
        "OLLAMA_URL",
        "LLM_MODEL",
        "EMBED_MODEL",
        "VISION_MODEL",
        "MAX_IMAGE_MB",
        "MAX_TEXT_FILE_MB",
        "MAX_LINK_RESPONSE_MB",
        "LINK_FETCH_TIMEOUT_SEC",
        "LINK_MAX_REDIRECTS",
        "DISABLE_LINK_FETCH",
        "DISABLE_OCR",
        "DISABLE_IMAGE_CAPTION",
        "CELERY_RESULT_BACKEND",
        "RRF_K",
        "RRF_TOPN",
        "DRAFT_TTL_HOURS",
        "YOUTUBE_API_KEY",
    ]

    for env_name in expected_env_names:
        assert f'"{env_name}"' in config_source


def test_load_settings_uses_spec_defaults() -> None:
    config_module = load_config_module()

    settings = config_module.load_settings({})

    assert settings.app_env == "dev"
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 8000
    assert settings.frontend_port == 8080
    assert settings.database_url == "postgresql+psycopg://sematrix:sematrix@postgres:5432/sematrix"
    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.ollama_url == "http://ollama:11434"
    assert settings.llm_model == "qwen3.5:9b"
    assert settings.embed_model == "bge-m3"
    assert settings.vision_model == "qwen3.5:9b"
    assert settings.max_image_mb == 10
    assert settings.max_text_file_mb == 2
    assert settings.max_link_response_mb == 2
    assert settings.link_fetch_timeout_sec == 10
    assert settings.link_max_redirects == 5
    assert settings.disable_link_fetch is False
    assert settings.disable_ocr is False
    assert settings.disable_image_caption is False
    assert settings.celery_result_backend == "redis://redis:6379/1"
    assert settings.rrf_k == 60
    assert settings.rrf_topn == 200
    assert settings.draft_ttl_hours == 24
    assert settings.youtube_api_key == ""


def test_load_settings_parses_overrides_and_types() -> None:
    config_module = load_config_module()

    settings = config_module.load_settings(
        {
            "APP_ENV": "prod",
            "API_HOST": "127.0.0.1",
            "API_PORT": "9000",
            "FRONTEND_PORT": "9001",
            "DATABASE_URL": "postgresql+psycopg://user:pass@db:5432/custom",
            "REDIS_URL": "redis://cache:6379/4",
            "OLLAMA_URL": "http://ollama:22434",
            "LLM_MODEL": "custom-llm",
            "EMBED_MODEL": "custom-embed",
            "VISION_MODEL": "custom-vision",
            "MAX_IMAGE_MB": "11",
            "MAX_TEXT_FILE_MB": "3",
            "MAX_LINK_RESPONSE_MB": "4",
            "LINK_FETCH_TIMEOUT_SEC": "12",
            "LINK_MAX_REDIRECTS": "6",
            "DISABLE_LINK_FETCH": "true",
            "DISABLE_OCR": "1",
            "DISABLE_IMAGE_CAPTION": "yes",
            "CELERY_RESULT_BACKEND": "redis://cache:6379/5",
            "RRF_K": "61",
            "RRF_TOPN": "201",
            "DRAFT_TTL_HOURS": "48",
            "YOUTUBE_API_KEY": "secret-key",
        }
    )

    assert settings.app_env == "prod"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 9000
    assert settings.frontend_port == 9001
    assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/custom"
    assert settings.redis_url == "redis://cache:6379/4"
    assert settings.ollama_url == "http://ollama:22434"
    assert settings.llm_model == "custom-llm"
    assert settings.embed_model == "custom-embed"
    assert settings.vision_model == "custom-vision"
    assert settings.max_image_mb == 11
    assert settings.max_text_file_mb == 3
    assert settings.max_link_response_mb == 4
    assert settings.link_fetch_timeout_sec == 12
    assert settings.link_max_redirects == 6
    assert settings.disable_link_fetch is True
    assert settings.disable_ocr is True
    assert settings.disable_image_caption is True
    assert settings.celery_result_backend == "redis://cache:6379/5"
    assert settings.rrf_k == 61
    assert settings.rrf_topn == 201
    assert settings.draft_ttl_hours == 48
    assert settings.youtube_api_key == "secret-key"


def test_load_settings_rejects_invalid_values() -> None:
    config_module = load_config_module()

    for environ in [
        {"APP_ENV": "staging"},
        {"API_PORT": "nope"},
        {"DISABLE_OCR": "maybe"},
    ]:
        try:
            config_module.load_settings(environ)
        except ValueError:
            continue

        raise AssertionError(f"Expected ValueError for environment {environ}")
