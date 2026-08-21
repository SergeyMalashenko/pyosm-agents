"""Conversion of transport and validation failures to stable tool errors."""

from __future__ import annotations

import httpx
from pydantic import ValidationError

from .schemas import ToolError


class OsmServiceError(RuntimeError):
    """A classified failure returned by an OpenStreetMap-backed service."""

    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def exception_to_tool_error(exc: Exception) -> ToolError:
    """Map implementation-specific exceptions to a public error contract."""

    if isinstance(exc, ValidationError):
        return ToolError(code="invalid_arguments", message=str(exc))
    if isinstance(exc, LookupError):
        return ToolError(code="not_found", message=str(exc))
    if isinstance(exc, OsmServiceError):
        return ToolError(
            code=exc.code,
            message=str(exc),
            retryable=exc.retryable,
        )
    if isinstance(exc, httpx.TimeoutException):
        return ToolError(
            code="upstream_timeout",
            message="The OpenStreetMap service request timed out",
            retryable=True,
        )
    if isinstance(exc, httpx.HTTPError):
        return ToolError(
            code="network_error",
            message=str(exc),
            retryable=True,
        )
    return ToolError(
        code="internal_error",
        message="Unexpected error while executing the OpenStreetMap tool",
    )
