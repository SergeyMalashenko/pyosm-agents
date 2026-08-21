"""Async clients for Nominatim and Overpass API endpoints."""

from __future__ import annotations

import asyncio
import copy
import json
import math
import os
import time
from collections import OrderedDict
from collections.abc import Mapping
from typing import Any, Protocol

import httpx
from typing_extensions import Self

from .errors import OsmServiceError

DEFAULT_NOMINATIM_URL = "https://nominatim.openstreetmap.org"
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_USER_AGENT = (
    "pyosm-agents/0.1 (+https://github.com/SergeyMalashenko/pyosm-agents)"
)


class OsmClient(Protocol):
    """Minimal client contract consumed by the framework-neutral tools."""

    async def geocode(
        self,
        query: str,
        *,
        limit: int,
        country_codes: list[str],
        language: str,
        include_geometry: bool,
    ) -> list[dict[str, Any]]: ...

    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
        *,
        zoom: int,
        language: str,
        include_geometry: bool,
    ) -> dict[str, Any] | None: ...

    async def search_nearby(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_m: int,
        tags: Mapping[str, str | None],
        limit: int,
    ) -> list[dict[str, Any]]: ...

    async def close(self) -> None: ...


def build_overpass_query(
    latitude: float,
    longitude: float,
    *,
    radius_m: int,
    tags: Mapping[str, str | None],
    limit: int,
) -> str:
    """Build a bounded Overpass QL query without accepting arbitrary QL."""

    filters = "".join(
        f"[{json.dumps(key)}]"
        if value is None
        else f"[{json.dumps(key)}={json.dumps(value, ensure_ascii=False)}]"
        for key, value in tags.items()
    )
    around = f"(around:{radius_m},{latitude:.7f},{longitude:.7f})"
    selectors = "\n".join(
        f"  {element_type}{around}{filters};"
        for element_type in ("node", "way", "relation")
    )
    return f"[out:json][timeout:25];\n(\n{selectors}\n);\nout tags center qt {limit};"


class OsmHttpClient:
    """Policy-conscious HTTP implementation for public or self-hosted APIs.

    Calls to Nominatim are serialized and separated by at least one second by
    default. Successful Nominatim responses are cached in memory so repeated
    identical agent calls do not hit the public service again.
    """

    def __init__(
        self,
        *,
        nominatim_url: str | None = None,
        overpass_url: str | None = None,
        user_agent: str | None = None,
        contact_email: str | None = None,
        timeout_s: float = 30.0,
        nominatim_min_interval_s: float = 1.0,
        cache_size: int = 512,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if nominatim_min_interval_s < 0:
            raise ValueError("nominatim_min_interval_s cannot be negative")
        if cache_size < 0:
            raise ValueError("cache_size cannot be negative")

        self.nominatim_url = (
            nominatim_url or os.getenv("PYOSM_NOMINATIM_URL") or DEFAULT_NOMINATIM_URL
        ).rstrip("/")
        self.overpass_url = (
            overpass_url or os.getenv("PYOSM_OVERPASS_URL") or DEFAULT_OVERPASS_URL
        )
        self.user_agent = (
            user_agent or os.getenv("PYOSM_USER_AGENT") or DEFAULT_USER_AGENT
        )
        self.contact_email = contact_email or os.getenv("PYOSM_CONTACT_EMAIL")
        self._headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        self._http = http_client or httpx.AsyncClient(timeout=timeout_s)
        self._owns_http_client = http_client is None
        self._nominatim_lock = asyncio.Lock()
        self._last_nominatim_request = -math.inf
        self._nominatim_min_interval_s = nominatim_min_interval_s
        self._cache_size = cache_size
        self._cache: OrderedDict[str, Any] = OrderedDict()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http_client:
            await self._http.aclose()

    async def geocode(
        self,
        query: str,
        *,
        limit: int,
        country_codes: list[str],
        language: str,
        include_geometry: bool,
    ) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "namedetails": 1,
            "limit": limit,
            "accept-language": language,
        }
        if country_codes:
            params["countrycodes"] = ",".join(country_codes)
        if include_geometry:
            params["polygon_geojson"] = 1
        if self.contact_email:
            params["email"] = self.contact_email

        payload = await self._nominatim_get("/search", params)
        if not isinstance(payload, list):
            raise OsmServiceError(
                "upstream_response_error",
                "Nominatim returned an unexpected search response",
                retryable=True,
            )
        return [item for item in payload if isinstance(item, dict)]

    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
        *,
        zoom: int,
        language: str,
        include_geometry: bool,
    ) -> dict[str, Any] | None:
        params: dict[str, str | int | float] = {
            "lat": latitude,
            "lon": longitude,
            "format": "jsonv2",
            "addressdetails": 1,
            "namedetails": 1,
            "zoom": zoom,
            "accept-language": language,
        }
        if include_geometry:
            params["polygon_geojson"] = 1
        if self.contact_email:
            params["email"] = self.contact_email

        payload = await self._nominatim_get("/reverse", params)
        if isinstance(payload, dict) and payload.get("error"):
            return None
        if not isinstance(payload, dict):
            raise OsmServiceError(
                "upstream_response_error",
                "Nominatim returned an unexpected reverse response",
                retryable=True,
            )
        return payload

    async def search_nearby(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_m: int,
        tags: Mapping[str, str | None],
        limit: int,
    ) -> list[dict[str, Any]]:
        query = build_overpass_query(
            latitude,
            longitude,
            radius_m=radius_m,
            tags=tags,
            limit=limit,
        )
        response = await self._http.post(
            self.overpass_url,
            data={"data": query},
            headers=self._headers,
        )
        self._raise_for_status(response, service="Overpass")
        payload = self._decode_json(response, service="Overpass")
        if not isinstance(payload, dict) or not isinstance(
            payload.get("elements"), list
        ):
            raise OsmServiceError(
                "upstream_response_error",
                "Overpass returned an unexpected response",
                retryable=True,
            )
        return [item for item in payload["elements"] if isinstance(item, dict)]

    async def _nominatim_get(
        self,
        path: str,
        params: Mapping[str, str | int | float],
    ) -> Any:
        cache_key = json.dumps([path, params], sort_keys=True, ensure_ascii=False)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        async with self._nominatim_lock:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

            delay = self._nominatim_min_interval_s - (
                time.monotonic() - self._last_nominatim_request
            )
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                response = await self._http.get(
                    f"{self.nominatim_url}{path}",
                    params=params,
                    headers=self._headers,
                )
            finally:
                self._last_nominatim_request = time.monotonic()

            self._raise_for_status(response, service="Nominatim")
            payload = self._decode_json(response, service="Nominatim")
            self._cache_put(cache_key, payload)
            return copy.deepcopy(payload)

    def _cache_get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return copy.deepcopy(self._cache[key])

    def _cache_put(self, key: str, value: Any) -> None:
        if self._cache_size == 0:
            return
        self._cache[key] = copy.deepcopy(value)
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    @staticmethod
    def _decode_json(response: httpx.Response, *, service: str) -> Any:
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise OsmServiceError(
                "upstream_response_error",
                f"{service} returned invalid JSON",
                retryable=True,
            ) from exc

    @staticmethod
    def _raise_for_status(response: httpx.Response, *, service: str) -> None:
        if response.is_success:
            return
        status = response.status_code
        if status == 429:
            code, retryable = "rate_limited", True
        elif status in {400, 404}:
            code, retryable = "upstream_rejected_request", False
        elif status >= 500:
            code, retryable = "service_unavailable", True
        else:
            code, retryable = "upstream_http_error", False
        raise OsmServiceError(
            code,
            f"{service} returned HTTP {status}",
            retryable=retryable,
        )
