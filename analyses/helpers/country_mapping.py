"""Auditable country normalization of validated coordinates; never modifies source data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from harmonize_core.countries import CountryLookup as SharedCountryLookup
from harmonize_core.countries import clean, name_key  # noqa: F401 -- re-exported

from analyses.helpers.publication import (
    AnalysisError,
    Settings,
    connect,
    image_table,
    table,
    text,
    unique_key,
)

VALIDATION_SOURCE = "geoharmonize coordinate validation (GADM GID_0)"
ISO_SOURCE = "pycountry 24.6.1 / ISO 3166-1"
MAP_SOURCE = "analyses/data/ne_110m_admin_0_countries.geojson"


class CountryLookup(SharedCountryLookup):
    """The shared harmonize-core lookup, with its locations as a DataFrame for audit joins."""

    def __init__(self, root: Path | None = None):
        # `root` is accepted for compatibility; the table ships with harmonize-core.
        super().__init__()
        self.locations = pd.DataFrame(
            [vars(location) for location in self.by_code.values()]
        ).set_index("country_code")


def eligible_country_records(settings: Settings) -> pd.DataFrame:
    """One row per eligible image, retaining the validated country attribution for audit.

    Countries come from the backend coordinate-validation table written by
    `geoharmonize integrate`, never from the raw locality fields. An image is
    eligible when its coordinate falls in exactly one GADM region and nothing
    contradicts that region's country:

    * COUNTRY_MATCH — the GADM country agrees with the recorded country. This
      includes ADM1_MISMATCH records, whose country is still validated even
      though their state or province is not.
    * COUNTRY_NOT_PROVIDED — no country was recorded, so the single GADM region
      stands unopposed. These images carry a mapped coordinate, so excluding
      them would leave a country blank here while its images appear on the
      validated-coordinate grid.

    COUNTRY_MISMATCH, NO_REFERENCE_MATCH, AMBIGUOUS_REFERENCE and unevaluated
    coordinates are never eligible.
    """
    with connect(settings) as connection:
        images = image_table(connection, settings)
        taxonomy = table(
            connection,
            settings,
            "taxonomy",
            (
                "img_id",
                "update_status",
                "accepted_species_name",
                "accepted_rank",
                "accepted_name",
            ),
        )
        coordinates = table(
            connection,
            settings,
            "coordinates",
            ("source_id", "country_check", "reference_gid_0", "reference_country"),
        )
        unique_key(connection, taxonomy, "img_id")
        unique_key(connection, coordinates, "source_id")
        return connection.execute(f"""
            WITH eligible AS (
                SELECT i.img_id, c.reference_gid_0 AS reference_code,
                    c.reference_country AS reference_country,
                    CASE WHEN c.country_check = 'COUNTRY_NOT_PROVIDED'
                        THEN 'imputed from coordinates'
                        ELSE 'validated against recorded country' END AS country_source,
                    coalesce({text("t.accepted_species_name")},
                        CASE WHEN lower(t.accepted_rank) = 'species'
                            THEN {text("t.accepted_name")} END) AS species
                FROM {images} i
                JOIN {taxonomy} t USING (img_id)
                JOIN {coordinates} c ON i.img_id = c.source_id
                WHERE t.update_status = 'MATCHED'
                    AND c.country_check IN ('COUNTRY_MATCH', 'COUNTRY_NOT_PROVIDED')
            )
            SELECT * FROM eligible WHERE species IS NOT NULL
        """).df()


def country_summaries(records: pd.DataFrame, features: list, lookup: CountryLookup):
    """Normalize before species deduplication, and retain a full attribution audit."""
    records = records.copy()
    # Empty strings represent missing values in audit grouping; literal 'NA'
    # remains Namibia. Preserve case/spacing of nonmissing references for review.
    for column in ("reference_code", "reference_country"):
        records[column] = records[column].fillna("")
    originals = records[["reference_code", "reference_country"]].drop_duplicates()
    if "country_source" not in records:
        raise AnalysisError("Country records must record how each country was resolved.")
    polygon_codes = {lookup.feature_code(f) for f in features} - {None}
    rows = []
    for original in originals.itertuples(index=False):
        code, method = lookup.resolve(original.reference_code, original.reference_country)
        location = lookup.locations.loc[code] if code else None
        representation = (
            "unresolved" if code is None else ("polygon" if code in polygon_codes else "marker")
        )
        rows.append(
            {
                "reference_code": original.reference_code,
                "reference_country": original.reference_country,
                "country_code": code or "",
                "country_name": location.country_name if code else "Unresolved",
                "resolution_method": method,
                "representation": representation,
                "mapping_source": (
                    "unresolved"
                    if code is None
                    else VALIDATION_SOURCE
                    + "; "
                    + ISO_SOURCE
                    + "; harmonize_core/countries.py; harmonize_core/data/country_locations.csv"
                ),
                "location_source": (
                    MAP_SOURCE
                    if representation == "polygon"
                    else location.source
                    if representation == "marker"
                    else ""
                ),
                "location_feature": location.source_feature if representation == "marker" else "",
            }
        )
    fields = [
        "reference_code",
        "reference_country",
        "country_code",
        "country_name",
        "resolution_method",
        "representation",
        "mapping_source",
        "location_source",
        "location_feature",
    ]
    mappings = pd.DataFrame(rows, columns=fields)
    records = records.merge(mappings, on=fields[:2], how="left", validate="many_to_one")
    # The audit separates countries read from the record from countries imputed
    # from the coordinate alone, so an imputed total is never mistaken for a
    # country the collector wrote down.
    audit = (
        records.groupby([*fields[:2], "country_source", *fields[2:]], dropna=False, sort=True)
        .agg(
            image_count=("img_id", "size"),
            species_count=("species", "nunique"),
        )
        .reset_index()
    )
    # Do not sum per-reference species counts: the same species may occur under
    # several GADM codes (disputed areas) that normalize to one country.
    richness = (
        records.groupby(
            ["country_code", "country_name", "representation"],
            dropna=False,
        )
        .agg(species_count=("species", "nunique"), image_count=("img_id", "size"))
        .reset_index()
    )
    richness["mapped"] = richness["representation"] != "unresolved"
    richness = richness.sort_values(["species_count", "country_code"], ascending=[False, True])
    return richness, audit
