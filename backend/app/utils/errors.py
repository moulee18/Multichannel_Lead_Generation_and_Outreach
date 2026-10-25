from __future__ import annotations

from fastapi import HTTPException, status


class GrowthOSError(Exception):
    """Base application exception."""

    def __init__(self, message: str, code: str = "GROWTHOS_ERROR", details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class SourceRestrictionError(GrowthOSError):
    """Raised when an external source blocks automated access, lacks credentials, or hits quota."""

    def __init__(self, message: str, source: str, restriction_type: str = "API_RESTRICTED", details: dict | None = None):
        super().__init__(
            message=message,
            code=restriction_type,
            details={"source": source, **(details or {})},
        )


class IntegrityViolationError(GrowthOSError):
    """Raised when an operation violates non-negotiable integrity rules (e.g. non-allowlisted outbound recipient)."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, code="INTEGRITY_VIOLATION", details=details)


def to_http_exception(err: GrowthOSError, status_code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": err.code,
            "message": err.message,
            "details": err.details,
        },
    )
