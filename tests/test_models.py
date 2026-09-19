from colharmonize.models import (
    Adm1Check,
    CoordinateCheck,
    CoordinateValidationStatus,
    CountryCheck,
    MatchMethod,
    UpdateStatus,
)


def test_every_update_status_has_a_description() -> None:
    assert all(status.description for status in UpdateStatus)
    assert "accepted taxon" in UpdateStatus.MATCHED.description


def test_every_match_method_has_a_description() -> None:
    assert all(method.description for method in MatchMethod)
    assert "synonym" in MatchMethod.EXACT_SYNONYM.description
    assert "genus and epithet" in MatchMethod.FUZZY_TYPO.description


def test_every_coordinate_enum_has_a_description() -> None:
    assert all(value.description for value in CoordinateCheck)
    assert all(value.description for value in CountryCheck)
    assert all(value.description for value in Adm1Check)
    assert all(value.description for value in CoordinateValidationStatus)
