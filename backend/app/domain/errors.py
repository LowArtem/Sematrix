from __future__ import annotations


class DomainError(Exception):
    status_code = 400
    code = "domain_error"
    message = "Request failed"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"
    message = "Resource not found"


class BadRequestError(DomainError):
    status_code = 400
    code = "bad_request"
    message = "Bad request"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"
    message = "Conflict"


class PayloadTooLargeError(DomainError):
    status_code = 413
    code = "payload_too_large"
    message = "Payload too large"


class UnsupportedMediaTypeError(DomainError):
    status_code = 415
    code = "unsupported_media_type"
    message = "Unsupported media type"
