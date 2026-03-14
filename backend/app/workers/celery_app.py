from __future__ import annotations

import contextvars
from datetime import timedelta
from typing import Any

from celery import Celery
from celery.signals import task_postrun, task_prerun

from app.core import bind_log_context, configure_logging, get_logger, get_settings, reset_log_context


configure_logging()
logger = get_logger(__name__)
_TASK_CONTEXT_TOKENS: dict[str, dict[str, contextvars.Token[Any | None]]] = {}


settings = get_settings()


celery_app = Celery(
    "sematrix",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_default_queue="sematrix",
    timezone="UTC",
    beat_schedule={
        "draft-cleanup": {
            "task": "sematrix.cleanup_drafts",
            "schedule": timedelta(hours=settings.draft_ttl_hours),
        }
    },
    worker_hijack_root_logger=False,
)


@task_prerun.connect
def log_task_start(
    task_id: str | None = None,
    task=None,
    args=None,
    kwargs=None,
    **_: object,
) -> None:
    active_kwargs = kwargs or {}
    context_tokens = bind_log_context(
        task_id=task_id,
        note_id=active_kwargs.get("note_id"),
        index_version=active_kwargs.get("index_version"),
    )
    if task_id is not None:
        _TASK_CONTEXT_TOKENS[task_id] = context_tokens

    logger.info(
        "task_started",
        extra={
            "event": "task_started",
            "task_id": task_id,
            "task_name": getattr(task, "name", None),
        },
    )


@task_postrun.connect
def log_task_finish(
    task_id: str | None = None,
    task=None,
    state: str | None = None,
    **_: object,
) -> None:
    logger.info(
        "task_finished",
        extra={
            "event": "task_finished",
            "task_id": task_id,
            "task_name": getattr(task, "name", None),
            "task_state": state,
        },
    )

    context_tokens = None if task_id is None else _TASK_CONTEXT_TOKENS.pop(task_id, None)
    if context_tokens is not None:
        reset_log_context(context_tokens)
