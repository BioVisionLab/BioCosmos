from geoharmonize.models import (
    Adm1Check,
    CoordinateCheck,
    CoordinateValidationStatus,
    CountryCheck,
)


def test_every_coordinate_enum_has_a_description() -> None:
    assert all(value.description for value in CoordinateCheck)
    assert all(value.description for value in CountryCheck)
    assert all(value.description for value in Adm1Check)
    assert all(value.description for value in CoordinateValidationStatus)
