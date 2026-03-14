from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request

from app.core.logging import bind_log_context, get_logger, reset_log_context


logger = get_logger(__name__)


def register_request_context_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid4())
        request.state.request_id = request_id
        context_tokens = bind_log_context(request_id=request_id)
        started_at = perf_counter()

        logger.info(
            "api_request_started",
            extra={
                "event": "api_request_started",
                "method": request.method,
                "path": request.url.path,
            },
        )

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "api_request_failed",
                extra={
                    "event": "api_request_failed",
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": int((perf_counter() - started_at) * 1000),
                },
            )
            reset_log_context(context_tokens)
            raise

        response.headers["X-Request-Id"] = request_id
        logger.info(
            "api_request_finished",
            extra={
                "event": "api_request_finished",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": int((perf_counter() - started_at) * 1000),
            },
        )
        reset_log_context(context_tokens)
        return response
