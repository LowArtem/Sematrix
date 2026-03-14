from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dto import ApiErrorDto


_STATUS_ERROR_MAP: dict[int, tuple[str, str]] = {
    404: ("not_found", "Resource not found"),
    409: ("conflict", "Conflict"),
    413: ("payload_too_large", "Payload too large"),
    415: ("unsupported_media_type", "Unsupported media type"),
    422: ("validation_error", "Request validation failed"),
    500: ("internal_server_error", "Internal server error"),
}


def _build_error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    payload = ApiErrorDto(code=code, message=message, details=details)
    content = payload.model_dump(exclude_none=True)
    return JSONResponse(status_code=status_code, content=content)


def _format_validation_details(exc: RequestValidationError) -> list[dict[str, str]]:
    return [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]


def _resolve_http_error(exc: StarletteHTTPException) -> tuple[str, str, Any | None]:
    default_code, default_message = _STATUS_ERROR_MAP.get(
        exc.status_code,
        ("http_error", "Request failed"),
    )

    if exc.status_code in _STATUS_ERROR_MAP:
        return default_code, default_message, None

    if isinstance(exc.detail, str) and exc.detail.strip():
        return default_code, exc.detail, None

    return default_code, default_message, exc.detail


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request
        return _build_error_response(
            status_code=422,
            code="validation_error",
            message="Request validation failed",
            details={"errors": _format_validation_details(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        del request
        code, message, details = _resolve_http_error(exc)
        return _build_error_response(
            status_code=exc.status_code,
            code=code,
            message=message,
            details=details,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        del request
        del exc
        return _build_error_response(
            status_code=500,
            code="internal_server_error",
            message="Internal server error",
        )
