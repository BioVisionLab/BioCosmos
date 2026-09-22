"""Scientific counts and transparent country-to-map attribution."""

import json

import duckdb
import pandas as pd
import pycountry
import pytest
from analyses.helpers.country_mapping import (
    CountryLookup,
    country_summaries,
    eligible_country_records,
)
from analyses.helpers.publication import AnalysisError, project_root


@pytest.fixture
def lookup():
    return CountryLookup()


@pytest.fixture
def features():
    return json.loads(
        (project_root() / "analyses/data/ne_110m_admin_0_countries.geojson").read_text()
    )["features"]


@pytest.mark.parametrize(
    "code,name,expected,method",
    [
        (" us ", "", "US", "normalized code"),
        ("USA", "", "US", "normalized code"),
        ("NA", "", "NA", "normalized code"),
        ("UK", "", "GB", "alias"),
        ("CN-TW", "", "TW", "alias"),
        ("FR-973", "", "GF", "alias"),
        (None, "  Singapore  ", "SG", "country-name fallback"),
        ("ZZ", "United States", "US", "country-name fallback"),
        ("unknown", "Kosovo", "XK", "country-name fallback"),
        ("US", "Canada", "US", "normalized code"),
        (None, "", None, "unresolved"),
        ("ZZ", None, None, "unresolved"),
        ("ZZ", "Korea", None, "unresolved"),
        ("ZZ", "Singapor", None, "unresolved"),
    ],
)
def test_exact_normalization(lookup, code, name, expected, method):
    assert lookup.resolve(code, name) == (expected, method)


def test_taiwan_and_missing_polygons(lookup, features):
    taiwan = next(f for f in features if f["properties"]["NAME"] == "Taiwan")
    assert lookup.feature_code(taiwan) == "TW"
    codes = {lookup.feature_code(f) for f in features}
    assert "TW" in codes
    assert not {"SG", "AX", "GF", "UM"} & codes


def test_unlabeled_polygons_take_the_country_gadm_files_them_under(lookup, features):
    # GADM records Somaliland coordinates under Somalia, and the 110m basemap draws
    # Somaliland as its own ISO-less polygon: shade it with Somalia's total.
    somaliland = next(f for f in features if f["properties"]["NAME"] == "Somaliland")
    assert somaliland["properties"]["ISO_A2"] == "-99"
    assert lookup.feature_code(somaliland) == "SO"
    # Nothing else is guessed: N. Cyprus stays unmapped.
    cyprus = next(f for f in features if f["properties"]["NAME"] == "N. Cyprus")
    assert lookup.feature_code(cyprus) is None


def test_complete_marker_lookup(lookup):
    assert set(lookup.locations.index) == {c.alpha_2 for c in pycountry.countries} | {"XK"}
    assert lookup.locations.longitude.between(-180, 180).all()
    assert lookup.locations.latitude.between(-90, 90).all()
    assert lookup.locations.source.str.contains("/v5.1.2/geojson/ne_10m_admin_0_").all()
    assert lookup.locations.loc["UM", "source_feature"] == "U.S. Minor Outlying Is."


def test_alias_merging_and_complete_audit(lookup, features):
    records = pd.DataFrame(
        [
            ("i1", "US", "", "Species one"),
            ("i2", " usa ", "", "Species one"),
            ("i3", "ZZ", "United States", "Species two"),
            ("i4", "SG", "Singapore", "Species one"),
            ("i5", "CN-TW", "", "Species one"),
            ("i6", "GF", "", "Species one"),
            ("i7", "ZZ", "", "Species one"),
            ("i8", None, None, "Species two"),
            ("i9", "AX", "", "Species one"),
            ("i10", "UM", "", "Species one"),
            ("i11", "FR", "", "Species three"),
        ],
        columns=["img_id", "reference_code", "reference_country", "species"],
    )
    records["country_source"] = "validated against recorded country"
    richness, audit = country_summaries(records, features, lookup)
    by_code = richness.set_index("country_code")
    assert by_code.loc["US", "image_count"] == 3
    assert by_code.loc["US", "species_count"] == 2
    assert by_code.loc["TW", "representation"] == "polygon"
    assert (by_code.loc[["SG", "GF", "AX", "UM"], "representation"] == "marker").all()
    assert by_code.loc["FR", "species_count"] == 1  # GF never merged into France
    assert by_code.loc["", "image_count"] == 2
    assert richness.image_count.sum() == audit.image_count.sum() == len(records)
    assert len(audit) == len(records)
    assert (audit.loc[audit.representation != "unresolved", "location_source"] != "").all()
    assert set(audit.reference_code) >= {"US", " usa ", "ZZ", ""}


def test_countries_come_from_validated_coordinates(settings, lookup, features):
    with duckdb.connect(str(settings.database)) as connection:
        connection.execute("""
            -- An ADM1 mismatch still has a validated country.
            UPDATE image_meta_coordinates SET validation_status = 'ADM1_MISMATCH',
                country_check = 'COUNTRY_MATCH', latitude = 50, longitude = -100,
                reference_gid_0 = 'CAN', reference_country = 'Canada' WHERE source_id = 'i3';
            -- GADM's non-ISO Kosovo code resolves by its exact reference name.
            UPDATE image_meta_coordinates SET validation_status = 'VALID',
                country_check = 'COUNTRY_MATCH', latitude = 42.6, longitude = 20.9,
                reference_gid_0 = 'XKO', reference_country = 'Kosovo' WHERE source_id = 'i7';
            -- Recorded locality countries are ignored, even when they disagree.
            UPDATE image_meta_locality SET country_code = 'FR', country = 'France';
        """)
    records = eligible_country_records(settings)
    assert set(records.img_id) == {"i1", "i2", "i3", "i7"}
    richness, audit = country_summaries(records, features, lookup)
    by_code = richness.set_index("country_code")
    assert by_code.species_count.to_dict() == {"US": 1, "CA": 1, "XK": 1}
    assert by_code.image_count.to_dict() == {"US": 2, "CA": 1, "XK": 1}
    assert (
        audit.loc[audit.reference_code == "XKO", "resolution_method"].item()
        == "country-name fallback"
    )
    assert audit.loc[audit.reference_code == "USA", "resolution_method"].item() == (
        "normalized code"
    )
    assert audit.mapping_source.str.startswith("geoharmonize coordinate validation").all()


@pytest.mark.parametrize(
    "status,check,eligible",
    [
        # The coordinate lies in another country than the one recorded.
        ("COUNTRY_MISMATCH", "COUNTRY_MISMATCH", False),
        ("NO_REFERENCE_MATCH", "NO_REFERENCE_MATCH", False),
        ("MISSING_COORDINATE", "NOT_EVALUATED", False),
        # No country was recorded, so the single GADM region stands unopposed.
        # These images appear on the validated-coordinate grid, so a country map
        # that dropped them would leave their country blank.
        ("VALID", "COUNTRY_NOT_PROVIDED", True),
    ],
)
def test_country_eligibility_follows_the_country_check(settings, status, check, eligible):
    with duckdb.connect(str(settings.database)) as connection:
        connection.execute(
            "UPDATE image_meta_coordinates SET validation_status = ?, country_check = ?, "
            "latitude = 50, longitude = -100, reference_gid_0 = 'CAN', "
            "reference_country = 'Canada' WHERE source_id = 'i3'",
            [status, check],
        )
    expected = {"i1", "i2", "i3"} if eligible else {"i1", "i2"}
    assert set(eligible_country_records(settings).img_id) == expected


def test_missing_country_is_imputed_from_the_coordinate_and_audited(settings, lookup, features):
    with duckdb.connect(str(settings.database)) as connection:
        # No country was recorded; the coordinate falls in exactly one GADM region.
        connection.execute("""
            UPDATE image_meta_coordinates SET validation_status = 'VALID',
                country_check = 'COUNTRY_NOT_PROVIDED', latitude = 50, longitude = -100,
                reference_gid_0 = 'CAN', reference_country = 'Canada' WHERE source_id = 'i3';
            UPDATE image_meta_locality SET country_code = NULL, country = NULL
                WHERE img_id = 'i3';
        """)
    records = eligible_country_records(settings)
    assert dict(zip(records.img_id, records.country_source)) == {
        "i1": "validated against recorded country",
        "i2": "validated against recorded country",
        "i3": "imputed from coordinates",
    }
    richness, audit = country_summaries(records, features, lookup)
    assert richness.set_index("country_code").image_count.to_dict() == {"US": 2, "CA": 1}
    assert audit.loc[audit.reference_code == "CAN", "country_source"].item() == (
        "imputed from coordinates"
    )
    assert richness.image_count.sum() == audit.image_count.sum() == 3


def test_duplicate_coordinates_rejected(settings):
    with duckdb.connect(str(settings.database)) as connection:
        connection.execute(
            "INSERT INTO image_meta_coordinates SELECT * FROM image_meta_coordinates LIMIT 1"
        )
    with pytest.raises(AnalysisError, match="one nonblank row key"):
        eligible_country_records(settings)


def test_empty_eligible_population(lookup, features):
    records = pd.DataFrame(
        columns=["img_id", "reference_code", "reference_country", "country_source", "species"]
    )
    richness, audit = country_summaries(records, features, lookup)
    assert richness.empty and audit.empty
    assert "mapped" in richness and "resolution_method" in audit
