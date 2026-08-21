import pytest
from pydantic import ValidationError

from pyosm_agents.core import GeocodeInput, NearbySearchInput, ReverseGeocodeInput


def test_geocode_input_normalizes_country_codes_and_text() -> None:
    value = GeocodeInput(
        query="  Нижний Новгород  ",
        country_codes=[" RU ", "ru"],
        language=" ru ",
    )

    assert value.query == "Нижний Новгород"
    assert value.country_codes == ["ru"]
    assert value.language == "ru"


@pytest.mark.parametrize("country_code", ["r", "rus", "r1"])
def test_geocode_input_rejects_invalid_country_code(country_code: str) -> None:
    with pytest.raises(ValidationError):
        GeocodeInput(query="test", country_codes=[country_code])


def test_reverse_input_validates_coordinates() -> None:
    with pytest.raises(ValidationError):
        ReverseGeocodeInput(latitude=91, longitude=44)


def test_nearby_input_accepts_any_value_tag() -> None:
    value = NearbySearchInput(latitude=56, longitude=44, tags={"amenity": None})

    assert value.tags == {"amenity": None}


@pytest.mark.parametrize(
    "tags",
    [
        {},
        {"bad key": "value"},
        {"amenity": ""},
        {"a": "1", "b": "2", "c": "3", "d": "4", "e": "5", "f": "6"},
    ],
)
def test_nearby_input_rejects_unsafe_or_unbounded_tags(
    tags: dict[str, str | None],
) -> None:
    with pytest.raises(ValidationError):
        NearbySearchInput(latitude=56, longitude=44, tags=tags)


def test_nearby_input_rejects_excessive_radius() -> None:
    with pytest.raises(ValidationError):
        NearbySearchInput(
            latitude=56,
            longitude=44,
            tags={"amenity": "hospital"},
            radius_m=5001,
        )
