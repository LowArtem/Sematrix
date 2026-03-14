from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping


def _read_bool(environ: Mapping[str, str], name: str, default: bool) -> bool:
    raw_value = environ.get(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(f"{name} must be a boolean value")


def _read_int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw_value = environ.get(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _read_text(environ: Mapping[str, str], name: str, default: str) -> str:
    return environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    app_env: str
    api_host: str
    api_port: int
    frontend_port: int
    database_url: str
    redis_url: str
    ollama_url: str
    llm_model: str
    embed_model: str
    vision_model: str
    max_image_mb: int
    max_text_file_mb: int
    max_link_response_mb: int
    link_fetch_timeout_sec: int
    link_max_redirects: int
    disable_link_fetch: bool
    disable_ocr: bool
    disable_image_caption: bool
    celery_result_backend: str
    rrf_k: int
    rrf_topn: int
    draft_ttl_hours: int
    youtube_api_key: str


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    active_environ = os.environ if environ is None else environ

    app_env = _read_text(active_environ, "APP_ENV", "dev")
    if app_env not in {"dev", "prod"}:
        raise ValueError("APP_ENV must be one of: dev, prod")

    return Settings(
        app_env=app_env,
        api_host=_read_text(active_environ, "API_HOST", "0.0.0.0"),
        api_port=_read_int(active_environ, "API_PORT", 8000),
        frontend_port=_read_int(active_environ, "FRONTEND_PORT", 8080),
        database_url=_read_text(
            active_environ,
            "DATABASE_URL",
            "postgresql+psycopg://sematrix:sematrix@postgres:5432/sematrix",
        ),
        redis_url=_read_text(active_environ, "REDIS_URL", "redis://redis:6379/0"),
        ollama_url=_read_text(active_environ, "OLLAMA_URL", "http://ollama:11434"),
        llm_model=_read_text(active_environ, "LLM_MODEL", "qwen3.5:9b"),
        embed_model=_read_text(active_environ, "EMBED_MODEL", "bge-m3"),
        vision_model=_read_text(active_environ, "VISION_MODEL", "qwen3.5:9b"),
        max_image_mb=_read_int(active_environ, "MAX_IMAGE_MB", 10),
        max_text_file_mb=_read_int(active_environ, "MAX_TEXT_FILE_MB", 2),
        max_link_response_mb=_read_int(active_environ, "MAX_LINK_RESPONSE_MB", 2),
        link_fetch_timeout_sec=_read_int(active_environ, "LINK_FETCH_TIMEOUT_SEC", 10),
        link_max_redirects=_read_int(active_environ, "LINK_MAX_REDIRECTS", 5),
        disable_link_fetch=_read_bool(active_environ, "DISABLE_LINK_FETCH", False),
        disable_ocr=_read_bool(active_environ, "DISABLE_OCR", False),
        disable_image_caption=_read_bool(active_environ, "DISABLE_IMAGE_CAPTION", False),
        celery_result_backend=_read_text(
            active_environ,
            "CELERY_RESULT_BACKEND",
            "redis://redis:6379/1",
        ),
        rrf_k=_read_int(active_environ, "RRF_K", 60),
        rrf_topn=_read_int(active_environ, "RRF_TOPN", 200),
        draft_ttl_hours=_read_int(active_environ, "DRAFT_TTL_HOURS", 24),
        youtube_api_key=_read_text(active_environ, "YOUTUBE_API_KEY", ""),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
