from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


_LOG_CONTEXT_VARS: dict[str, contextvars.ContextVar[Any | None]] = {
    "request_id": contextvars.ContextVar("request_id", default=None),
    "task_id": contextvars.ContextVar("task_id", default=None),
    "note_id": contextvars.ContextVar("note_id", default=None),
    "index_version": contextvars.ContextVar("index_version", default=None),
}


class StructuredLogContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for field_name, context_var in _LOG_CONTEXT_VARS.items():
            if getattr(record, field_name, None) is None:
                setattr(record, field_name, context_var.get())
        return True


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field_name in (
            "event",
            "request_id",
            "task_id",
            "note_id",
            "index_version",
            "status",
            "processing_error",
            "task_name",
            "task_state",
            "pipeline_run_id",
            "stage_name",
            "target",
            "warning_code",
            "retryable",
            "method",
            "path",
            "status_code",
            "started_at",
            "duration_ms",
            "total_duration_ms",
            "stage_durations_ms",
        ):
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True, default=str)


def configure_logging() -> None:
    root_logger = logging.getLogger()
    existing_handler = next(
        (
            handler
            for handler in root_logger.handlers
            if getattr(handler, "_sematrix_structured_handler", False)
        ),
        None,
    )
    if existing_handler is not None:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler._sematrix_structured_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(StructuredJsonFormatter())
    handler.addFilter(StructuredLogContextFilter())

    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def bind_log_context(**values: Any) -> dict[str, contextvars.Token[Any | None]]:
    tokens: dict[str, contextvars.Token[Any | None]] = {}

    for field_name, value in values.items():
        context_var = _LOG_CONTEXT_VARS.get(field_name)
        if context_var is None or value is None:
            continue
        tokens[field_name] = context_var.set(value)

    return tokens


def reset_log_context(tokens: dict[str, contextvars.Token[Any | None]]) -> None:
    for field_name, token in tokens.items():
        _LOG_CONTEXT_VARS[field_name].reset(token)
