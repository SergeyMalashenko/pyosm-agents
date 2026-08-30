from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

PARCEL_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [
            [44.0018, 56.3286],
            [44.0024, 56.3286],
            [44.0024, 56.3291],
            [44.0018, 56.3291],
            [44.0018, 56.3286],
        ]
    ],
}


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
                "address": {
                    "city": "Нижний Новгород",
                    "country_code": "ru",
                },
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
            {
                "type": "way",
                "id": 403,
                "tags": {"building": "warehouse", "name": "Склад рядом"},
                "geometry": [
                    {"lat": 56.3287, "lon": 44.0100},
                    {"lat": 56.3287, "lon": 44.0105},
                    {"lat": 56.3290, "lon": 44.0105},
                    {"lat": 56.3290, "lon": 44.0100},
                    {"lat": 56.3287, "lon": 44.0100},
                ],
            },
            {
                "type": "node",
                "id": 404,
                "lat": 56.3288,
                "lon": 44.0400,
                "tags": {"amenity": "school", "name": "Далёкая школа"},
            },
            {
                "type": "way",
                "id": 405,
                "tags": {
                    "highway": "secondary",
                    "name": "Северная дорога",
                },
                "geometry": [
                    {"lat": 56.3350, "lon": 43.9800},
                    {"lat": 56.3350, "lon": 44.0300},
                ],
            },
            {
                "type": "way",
                "id": 406,
                "tags": {
                    "natural": "wood",
                    "name": "Лесной массив",
                    "leaf_type": "mixed",
                },
                "geometry": [
                    {"lat": 56.3270, "lon": 44.0090},
                    {"lat": 56.3270, "lon": 44.0110},
                    {"lat": 56.3290, "lon": 44.0110},
                    {"lat": 56.3290, "lon": 44.0090},
                    {"lat": 56.3270, "lon": 44.0090},
                ],
            },
            {
                "type": "way",
                "id": 407,
                "tags": {
                    "natural": "water",
                    "water": "lake",
                    "name": "Тестовое озеро",
                },
                "geometry": [
                    {"lat": 56.3270, "lon": 43.9940},
                    {"lat": 56.3270, "lon": 43.9960},
                    {"lat": 56.3290, "lon": 43.9960},
                    {"lat": 56.3290, "lon": 43.9940},
                    {"lat": 56.3270, "lon": 43.9940},
                ],
            },
            {
                "type": "way",
                "id": 408,
                "tags": {
                    "natural": "water",
                    "water": "river",
                    "name": "Тестовая река",
                },
                "geometry": [
                    {"lat": 56.3260, "lon": 44.0060},
                    {"lat": 56.3260, "lon": 44.0070},
                    {"lat": 56.3340, "lon": 44.0070},
                    {"lat": 56.3340, "lon": 44.0060},
                    {"lat": 56.3260, "lon": 44.0060},
                ],
            },
            {
                "type": "way",
                "id": 409,
                "tags": {
                    "waterway": "stream",
                    "name": "Тестовый ручей",
                    "intermittent": "yes",
                },
                "geometry": [
                    {"lat": 56.3250, "lon": 43.9970},
                    {"lat": 56.3330, "lon": 43.9990},
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
