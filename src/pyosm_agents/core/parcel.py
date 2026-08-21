"""Land-parcel geometry provider backed by pynspd."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pynspd import AsyncNspd
from shapely.geometry.base import BaseGeometry
from typing_extensions import Self

LAND_PARCEL_CATEGORY_ID = 36368


class ParcelNotFoundError(LookupError):
    """Raised when NSPD has no object for a cadastral number."""


class NotLandParcelError(ValueError):
    """Raised when a cadastral number identifies another EGRN object type."""


class ParcelGeometryError(ValueError):
    """Raised when NSPD does not publish usable parcel coordinates."""


@dataclass(frozen=True)
class ParcelRecord:
    """Land-parcel attributes required for combined OSM analysis."""

    cadastral_number: str
    geometry: BaseGeometry
    address: str | None = None
    declared_area_m2: float | None = None


class ParcelProvider(Protocol):
    """Minimal parcel source consumed by :class:`OsmTools`."""

    async def get_parcel(self, cadastral_number: str) -> ParcelRecord: ...

    async def close(self) -> None: ...


def _model_dump(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json", by_alias=True)
    return {}


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class NspdParcelProvider:
    """Resolve cadastral numbers to WGS84 geometries using pynspd."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = AsyncNspd()
        return self._client

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.close()
            self._client = None

    async def get_parcel(self, cadastral_number: str) -> ParcelRecord:
        feature = await self._get_client().find(cadastral_number)
        if feature is None:
            raise ParcelNotFoundError(
                f"Land parcel {cadastral_number} was not found in NSPD"
            )

        properties = getattr(feature, "properties", None)
        category = getattr(properties, "category", None)
        if category != LAND_PARCEL_CATEGORY_ID:
            raise NotLandParcelError(
                f"Cadastral number {cadastral_number} does not identify a land parcel"
            )

        options_obj = getattr(properties, "options", None)
        if bool(getattr(options_obj, "no_coords", False)):
            raise ParcelGeometryError(
                f"NSPD does not publish boundary coordinates for {cadastral_number}"
            )
        geometry_obj = getattr(feature, "geometry", None)
        to_shape = getattr(geometry_obj, "to_shape", None)
        if not callable(to_shape):
            raise ParcelGeometryError(
                f"NSPD does not publish usable geometry for {cadastral_number}"
            )
        geometry = to_shape()
        if geometry is None or geometry.is_empty:
            raise ParcelGeometryError(
                f"NSPD does not publish usable geometry for {cadastral_number}"
            )

        options = _model_dump(options_obj)
        declared_area = next(
            (
                _optional_float(options[key])
                for key in ("specified_area", "declared_area", "area")
                if options.get(key) not in (None, "")
            ),
            None,
        )
        return ParcelRecord(
            cadastral_number=cadastral_number,
            geometry=geometry,
            address=options.get("readable_address"),
            declared_area_m2=declared_area,
        )
