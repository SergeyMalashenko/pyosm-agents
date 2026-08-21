"""Conversion of transport and validation failures to stable tool errors."""

from __future__ import annotations

import logging

import httpx
from pydantic import ValidationError
from pynspd import errors as nspd_errors

from .parcel import NotLandParcelError, ParcelGeometryError, ParcelNotFoundError
from .schemas import ToolError
from .spatial import GeometryLimitError, GeometryUnavailableError

logger = logging.getLogger(__name__)


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
    if isinstance(exc, ParcelNotFoundError):
        return ToolError(code="not_found", message=str(exc))
    if isinstance(exc, NotLandParcelError):
        return ToolError(code="not_a_land_parcel", message=str(exc))
    if isinstance(exc, ParcelGeometryError):
        return ToolError(code="parcel_geometry_unavailable", message=str(exc))
    if isinstance(exc, GeometryLimitError):
        return ToolError(code="contour_too_large", message=str(exc))
    if isinstance(exc, GeometryUnavailableError):
        return ToolError(code="invalid_geometry", message=str(exc))
    if isinstance(exc, nspd_errors.NotFound):
        return ToolError(code="not_found", message=str(exc))
    if isinstance(exc, nspd_errors.BlockedIP):
        return ToolError(code="nspd_access_blocked", message=str(exc), retryable=True)
    if isinstance(exc, nspd_errors.TooManyRequests):
        return ToolError(code="nspd_rate_limited", message=str(exc), retryable=True)
    if isinstance(exc, nspd_errors.PynspdServerError):
        return ToolError(code="nspd_unavailable", message=str(exc), retryable=True)
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
    logger.error(
        "Unhandled exception while executing an OpenStreetMap tool",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return ToolError(
        code="internal_error",
        message="Unexpected error while executing the OpenStreetMap tool",
    )
