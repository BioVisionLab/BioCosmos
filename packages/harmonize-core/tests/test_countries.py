from __future__ import annotations

import pycountry
import pytest

from harmonize_core.countries import CountryLookup


@pytest.fixture(scope="module")
def lookup() -> CountryLookup:
    return CountryLookup()


@pytest.mark.parametrize(
    "code,name,expected,method",
    [
        ("USA", "", "US", "normalized code"),
        (" us ", "", "US", "normalized code"),
        # 'NA' is Namibia, never a missing value.
        ("NA", "", "NA", "normalized code"),
        ("UK", "", "GB", "alias"),
        ("CN-TW", "", "TW", "alias"),
        # GADM's non-ISO codes resolve only through an exact, unique name.
        ("XKO", "Kosovo", "XK", "country-name fallback"),
        ("Z01", "India", "IN", "country-name fallback"),
        ("Z01", "", None, "unresolved"),
        ("ZZ", "Korea", None, "unresolved"),
        (None, None, None, "unresolved"),
    ],
)
def test_resolve(lookup, code, name, expected, method):
    assert lookup.resolve(code, name) == (expected, method)


def test_feature_code_prefers_iso_and_maps_somaliland(lookup):
    assert lookup.feature_code({"properties": {"ISO_A2": "TW", "NAME": "Taiwan"}}) == "TW"
    somaliland = {"properties": {"ISO_A2": "-99", "ISO_A2_EH": "-99", "NAME": "Somaliland"}}
    assert lookup.feature_code(somaliland) == "SO"
    cyprus = {"properties": {"ISO_A2": "-99", "ISO_A2_EH": "-99", "NAME": "N. Cyprus"}}
    assert lookup.feature_code(cyprus) is None


def test_every_iso_country_has_a_location_and_display_name(lookup):
    assert set(lookup.by_code) == {c.alpha_2 for c in pycountry.countries} | {"XK"}
    assert lookup.country_name("BO") == "Bolivia"
    assert lookup.country_name("XK") == "Kosovo"
