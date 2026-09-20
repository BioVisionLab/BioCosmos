"""Human-readable descriptions for geoharmonize coordinate-validation codes.

The authoritative descriptions live on the ``CoordinateValidationStatus``,
``CoordinateCheck``, ``CountryCheck`` and ``Adm1Check`` StrEnums in
``geoharmonize.models``. They are mirrored rather than imported, the same way
``col_match_codes`` mirrors colharmonize: the backend does not depend on the
harmonization CLIs, and a test asserts the two copies agree.
"""

import logging

logger = logging.getLogger(__name__)

# Mirrors geoharmonize.models.CoordinateValidationStatus.description.
VALIDATION_STATUS_DESCRIPTIONS: dict[str, str] = {
    "MISSING_COORDINATE": "No coordinate was recorded.",
    "COORDINATE_OUT_OF_RANGE": (
        "The coordinate is outside the range of valid latitudes or longitudes."
    ),
    "ZERO_COORDINATE": "The coordinate is 0, 0.",
    "NO_REFERENCE_MATCH": "The coordinate falls outside every known boundary.",
    "AMBIGUOUS_REFERENCE": "The coordinate falls where several regions meet.",
    "COUNTRY_MISMATCH": (
        "The coordinate falls in a different country than the one recorded."
    ),
    "ADM1_MISMATCH": (
        "The coordinate falls in a different state or province than the one recorded."
    ),
    "VALID": "The coordinate matches the recorded locality.",
}

# Mirrors geoharmonize.models.CoordinateCheck.description.
COORDINATE_CHECK_DESCRIPTIONS: dict[str, str] = {
    "MISSING_COORDINATE": (
        "Latitude or longitude was missing, non-finite, or could not be parsed."
    ),
    "LATITUDE_OUT_OF_RANGE": "Latitude was outside -90 to 90 degrees.",
    "LONGITUDE_OUT_OF_RANGE": "Longitude was outside -180 to 180 degrees.",
    "ZERO_COORDINATE": "Both latitude and longitude were zero.",
    "VALID_COORDINATE": "Both coordinates were finite and in range.",
}

# Mirrors geoharmonize.models.CountryCheck.description.
COUNTRY_CHECK_DESCRIPTIONS: dict[str, str] = {
    "COUNTRY_MATCH": "Recorded and coordinate-derived countries agree.",
    "COUNTRY_MISMATCH": "Recorded and coordinate-derived countries differ.",
    "COUNTRY_NOT_PROVIDED": "No recorded country was supplied.",
    "NO_REFERENCE_MATCH": "The coordinate intersected no reference region.",
    "AMBIGUOUS_REFERENCE": (
        "The coordinate intersected multiple distinct reference regions."
    ),
    "NOT_EVALUATED": "Country was not checked because coordinates were invalid.",
}

# Mirrors geoharmonize.models.Adm1Check.description.
ADM1_CHECK_DESCRIPTIONS: dict[str, str] = {
    "ADM1_MATCH": "Recorded and coordinate-derived ADM1 values agree.",
    "ADM1_MISMATCH": "Recorded and coordinate-derived ADM1 values differ.",
    "ADM1_NOT_PROVIDED": "No recorded ADM1 value was supplied.",
    "NO_ADM1_REFERENCE_MATCH": "The reference region had no ADM1 name.",
    "NO_REFERENCE_MATCH": "The coordinate intersected no reference region.",
    "AMBIGUOUS_REFERENCE": (
        "The coordinate intersected multiple distinct reference regions."
    ),
    "NOT_EVALUATED": "ADM1 was not checked because coordinates were invalid.",
}

# The same code carries different prose in different groups --
# NO_REFERENCE_MATCH and AMBIGUOUS_REFERENCE appear in three of the four -- so
# the groups stay separate rather than being merged into one lookup.
_GROUPS: dict[str, dict[str, str]] = {
    "validationStatus": VALIDATION_STATUS_DESCRIPTIONS,
    "coordinateCheck": COORDINATE_CHECK_DESCRIPTIONS,
    "countryCheck": COUNTRY_CHECK_DESCRIPTIONS,
    "adm1Check": ADM1_CHECK_DESCRIPTIONS,
}


def _describe(group: str, code: str | None) -> str | None:
    if not code:
        return None
    return _GROUPS[group].get(code.strip().upper())


def describe_validation_status(code: str | None) -> str | None:
    """Return the prose for a final validation outcome."""
    return _describe("validationStatus", code)


def describe_coordinate_check(code: str | None) -> str | None:
    """Return the prose for a parsing or range check."""
    return _describe("coordinateCheck", code)


def describe_country_check(code: str | None) -> str | None:
    """Return the prose for a country comparison."""
    return _describe("countryCheck", code)


def describe_adm1_check(code: str | None) -> str | None:
    """Return the prose for an ADM1 comparison."""
    return _describe("adm1Check", code)


def all_descriptions() -> dict[str, dict[str, str]]:
    """The full code dictionary, as served by GET /geography/codes."""
    return {group: dict(codes) for group, codes in _GROUPS.items()}
