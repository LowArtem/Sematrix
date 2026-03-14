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


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"
    message = "Conflict"
