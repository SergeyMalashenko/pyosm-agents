from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from shapely.geometry import Polygon

from pyosm_agents.core.parcel import ParcelRecord


class FakeOsmClient:
    def __init__(self) -> None:
        self.closed = False
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.geocode_response: list[dict[str, Any]] = [
            {
                "place_id": 100,
                "osm_type": "relation",
                "osm_id": 200,
                "lat": "56.3287",
                "lon": "44.0020",
                "display_name": "Нижний Новгород, Россия",
                "name": "Нижний Новгород",
                "boundingbox": ["56.1", "56.5", "43.6", "44.3"],
                "category": "boundary",
                "type": "administrative",
                "importance": 0.8,
                "address": {"city": "Нижний Новгород", "country_code": "ru"},
                "geojson": {"type": "Polygon", "coordinates": []},
            }
        ]
        self.reverse_response: dict[str, Any] | None = self.geocode_response[0]
        self.nearby_response: list[dict[str, Any]] = [
            {
                "type": "node",
                "id": 300,
                "lat": 56.329,
                "lon": 44.002,
                "tags": {"amenity": "hospital", "name": "Больница"},
            },
            {
                "type": "way",
                "id": 301,
                "center": {"lat": 56.33, "lon": 44.003},
                "tags": {"amenity": "hospital", "name": "Корпус"},
            },
        ]
        self.polygon_response: list[dict[str, Any]] = [
            {
                "type": "node",
                "id": 400,
                "lat": 56.3288,
                "lon": 44.0021,
                "tags": {"amenity": "cafe", "name": "Кафе"},
            },
            {
                "type": "way",
                "id": 401,
                "tags": {"building": "yes", "name": "Здание"},
                "geometry": [
                    {"lat": 56.32875, "lon": 44.00205},
                    {"lat": 56.32875, "lon": 44.00215},
                    {"lat": 56.32885, "lon": 44.00215},
                    {"lat": 56.32885, "lon": 44.00205},
                    {"lat": 56.32875, "lon": 44.00205},
                ],
            },
            {
                "type": "way",
                "id": 402,
                "tags": {"highway": "service"},
                "geometry": [
                    {"lat": 56.3285, "lon": 44.0015},
                    {"lat": 56.3295, "lon": 44.0025},
                ],
            },
        ]

    async def geocode(
        self,
        query: str,
        *,
        limit: int,
        country_codes: list[str],
        language: str,
        include_geometry: bool,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "geocode",
                {
                    "query": query,
                    "limit": limit,
                    "country_codes": country_codes,
                    "language": language,
                    "include_geometry": include_geometry,
                },
            )
        )
        return self.geocode_response

    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
        *,
        zoom: int,
        language: str,
        include_geometry: bool,
    ) -> dict[str, Any] | None:
        self.calls.append(
            (
                "reverse_geocode",
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "zoom": zoom,
                    "language": language,
                    "include_geometry": include_geometry,
                },
            )
        )
        return self.reverse_response

    async def search_nearby(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_m: int,
        tags: Mapping[str, str | None],
        limit: int,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "search_nearby",
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius_m": radius_m,
                    "tags": dict(tags),
                    "limit": limit,
                },
            )
        )
        return self.nearby_response

    async def search_bbox(
        self,
        bounds: tuple[float, float, float, float],
        *,
        tag_filters: Sequence[Mapping[str, str | None]],
        limit: int,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "search_bbox",
                {
                    "bounds": bounds,
                    "tag_filters": [dict(value) for value in tag_filters],
                    "limit": limit,
                },
            )
        )
        return self.polygon_response[:limit]

    async def close(self) -> None:
        self.closed = True


class FakeParcelProvider:
    def __init__(self) -> None:
        self.closed = False
        self.queries: list[str] = []
        self.record = ParcelRecord(
            cadastral_number="52:24:0000000:2216",
            address="Нижегородская область, тестовый участок",
            declared_area_m2=10_000,
            geometry=Polygon(
                [
                    (44.0018, 56.3286),
                    (44.0024, 56.3286),
                    (44.0024, 56.3291),
                    (44.0018, 56.3291),
                    (44.0018, 56.3286),
                ]
            ),
        )

    async def get_parcel(self, cadastral_number: str) -> ParcelRecord:
        self.queries.append(cadastral_number)
        return self.record

    async def close(self) -> None:
        self.closed = True
