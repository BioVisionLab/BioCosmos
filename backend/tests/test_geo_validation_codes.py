"""Tests for the mirrored geoharmonize code descriptions.

The prose is hand-copied from the StrEnums in `geoharmonize.models`, so the
parity test below is the thing that stops the two drifting.
"""

import pytest

from app.services.geo_validation_codes import (
    ADM1_CHECK_DESCRIPTIONS,
    COORDINATE_CHECK_DESCRIPTIONS,
    COUNTRY_CHECK_DESCRIPTIONS,
    VALIDATION_STATUS_DESCRIPTIONS,
    all_descriptions,
    describe_adm1_check,
    describe_coordinate_check,
    describe_country_check,
    describe_validation_status,
)


def test_status_prose_is_one_short_sentence():
    """These are read in a tooltip, so each has to stay scannable."""
    for code, description in VALIDATION_STATUS_DESCRIPTIONS.items():
        assert description.count(".") == 1, code
        assert len(description) <= 90, (code, len(description))


def test_all_descriptions_has_the_four_groups():
    payload = all_descriptions()
    assert set(payload) == {
        "validationStatus",
        "coordinateCheck",
        "countryCheck",
        "adm1Check",
    }
    assert len(payload["validationStatus"]) == 8


def test_all_descriptions_returns_copies():
    """A caller must not be able to edit the module's own dicts."""
    original = VALIDATION_STATUS_DESCRIPTIONS["VALID"]
    all_descriptions()["validationStatus"]["VALID"] = "tampered"
    assert VALIDATION_STATUS_DESCRIPTIONS["VALID"] == original


@pytest.mark.parametrize(
    "describe,code",
    [
        (describe_validation_status, "VALID"),
        (describe_coordinate_check, "ZERO_COORDINATE"),
        (describe_country_check, "COUNTRY_MATCH"),
        (describe_adm1_check, "ADM1_MATCH"),
    ],
)
def test_describe_is_case_and_whitespace_insensitive(describe, code):
    assert describe(f"  {code.lower()}  ") == describe(code)


@pytest.mark.parametrize(
    "describe",
    [
        describe_validation_status,
        describe_coordinate_check,
        describe_country_check,
        describe_adm1_check,
    ],
)
def test_describe_returns_none_for_unknown_codes(describe):
    assert describe(None) is None
    assert describe("") is None
    assert describe("NOT_A_CODE") is None


def test_the_same_code_reads_differently_per_group():
    """NO_REFERENCE_MATCH is in three groups and means something different in each."""
    outcome = describe_validation_status("NO_REFERENCE_MATCH")
    country = describe_country_check("NO_REFERENCE_MATCH")
    adm1 = describe_adm1_check("NO_REFERENCE_MATCH")
    assert outcome != country
    assert country == adm1  # the two component checks do agree with each other


def test_descriptions_match_the_geoharmonize_enums():
    """The mirrored prose must not drift from the package it mirrors."""
    models = pytest.importorskip(
        "geoharmonize.models",
        reason="geoharmonize is a workspace member; install with `uv sync --all-packages`",
    )
    for mirrored, enum in (
        (VALIDATION_STATUS_DESCRIPTIONS, models.CoordinateValidationStatus),
        (COORDINATE_CHECK_DESCRIPTIONS, models.CoordinateCheck),
        (COUNTRY_CHECK_DESCRIPTIONS, models.CountryCheck),
        (ADM1_CHECK_DESCRIPTIONS, models.Adm1Check),
    ):
        assert set(mirrored) == {member.value for member in enum}
        for member in enum:
            assert mirrored[member.value] == member.description, member
