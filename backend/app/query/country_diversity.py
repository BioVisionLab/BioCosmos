"""Species diversity by validated country.

The same population and normalization as panel G of
`analyses/notebooks/data_summary.ipynb`, so the site and the published figure
agree country for country:

* Countries come from the `geoharmonize integrate` coordinate-validation table,
  never from the raw locality fields. An image counts when its coordinate falls
  in exactly one GADM region and nothing contradicts that region's country:
  COUNTRY_MATCH (including ADM1_MISMATCH records) or COUNTRY_NOT_PROVIDED, where
  the country is imputed from the coordinate.
* Only MATCHED taxonomy with an accepted species; subspecies group with their
  species and genus-only matches are left out.
* The GADM GID_0 code is normalized to ISO alpha-2 by the shared
  `harmonize_core.countries.CountryLookup` *before* species are deduplicated,
  because several GADM codes (disputed areas) can normalize to one country.
"""

import logging

import polars as pl
from harmonize_core.countries import CountryLookup

from ..configs.config import ColConfig, ImageMetaConfig, LocalityConfig
from ..database.duckdb import DuckDBClient

logger = logging.getLogger(__name__)

_ELIGIBLE_CHECKS = ("COUNTRY_MATCH", "COUNTRY_NOT_PROVIDED")


def _text(column: str) -> str:
    return f"nullif(trim(cast({column} AS VARCHAR)), '')"


class CountryDiversity:
    """Per-country species richness, computed once and then served from memory.

    The coordinate table is only ever written with the backend stopped, and
    the taxonomy is rebuilt at startup, so nothing this reads can change while
    the process is running.
    """

    def __init__(
        self, duckdb_client: DuckDBClient, lookup: CountryLookup | None = None
    ):
        self.db_client = duckdb_client
        self.lookup = lookup or CountryLookup()
        self.images_table = ImageMetaConfig().table
        self.taxonomy_table = ColConfig().occurrence_status_table
        self.coordinates_table = LocalityConfig().coordinates_table
        self._records: pl.DataFrame | None = None
        self._unresolved_images = 0

    def available(self) -> bool:
        return not self.db_client.missing_tables(
            [self.images_table, self.taxonomy_table, self.coordinates_table]
        )

    def _eligible_groups(self) -> pl.DataFrame:
        """Eligible images grouped by GADM reference, species and country source."""
        checks = ", ".join(f"'{check}'" for check in _ELIGIBLE_CHECKS)
        return self.db_client.execute(
            f"""
            WITH eligible AS (
                SELECT
                    coalesce(c.reference_gid_0, '') AS reference_code,
                    coalesce(c.reference_country, '') AS reference_country,
                    c.country_check = 'COUNTRY_NOT_PROVIDED' AS imputed,
                    coalesce({_text("t.accepted_species_name")},
                        CASE WHEN lower(t.accepted_rank) = 'species'
                            THEN {_text("t.accepted_name")} END) AS species
                FROM {self.images_table} i
                JOIN {self.taxonomy_table} t USING (img_id)
                JOIN {self.coordinates_table} c ON i.img_id = c.source_id
                WHERE t.update_status = 'MATCHED' AND c.country_check IN ({checks})
            )
            SELECT reference_code, reference_country, imputed, species,
                count(*)::BIGINT AS image_count
            FROM eligible WHERE species IS NOT NULL
            GROUP BY ALL
            """
        ).pl()

    def _load(self) -> pl.DataFrame:
        if self._records is not None:
            return self._records
        groups = self._eligible_groups()
        references = groups.select("reference_code", "reference_country").unique()
        codes = [
            self.lookup.resolve(row["reference_code"], row["reference_country"])[0]
            for row in references.iter_rows(named=True)
        ]
        mapping = references.with_columns(
            pl.Series("country_code", codes, dtype=pl.Utf8)
        )
        records = groups.join(
            mapping, on=["reference_code", "reference_country"], how="left"
        )
        self._unresolved_images = int(
            records.filter(pl.col("country_code").is_null())["image_count"].sum()
        )
        self._records = records.filter(pl.col("country_code").is_not_null())
        return self._records

    def summary(self) -> dict | None:
        """Every country with eligible records, richest first."""
        if not self.available():
            return None
        records = self._load()
        countries = (
            records.group_by("country_code")
            .agg(
                pl.col("species").n_unique().alias("speciesCount"),
                pl.col("image_count").sum().alias("imageCount"),
                pl.col("image_count")
                .filter(pl.col("imputed"))
                .sum()
                .alias("imputedImageCount"),
            )
            .sort(["speciesCount", "country_code"], descending=[True, False])
        )
        rows = [
            {
                "countryCode": row["country_code"],
                "countryName": self.lookup.country_name(row["country_code"]),
                "speciesCount": row["speciesCount"],
                "imageCount": row["imageCount"],
                "imputedImageCount": row["imputedImageCount"],
            }
            for row in countries.iter_rows(named=True)
        ]
        return {
            "countries": rows,
            "mappedImages": int(records["image_count"].sum()),
            "imputedImages": int(
                records.filter(pl.col("imputed"))["image_count"].sum()
            ),
            "unresolvedImages": self._unresolved_images,
        }

    def species(self, country_code: str) -> dict | None:
        """The species recorded in one country, most images first.

        None when the coordinate table is absent, the code is not an ISO
        country, or the country has no eligible records.
        """
        code = country_code.strip().upper()
        if code not in self.lookup.by_code or not self.available():
            return None
        records = self._load().filter(pl.col("country_code") == code)
        if records.is_empty():
            return None
        species = (
            records.group_by("species")
            .agg(
                pl.col("image_count").sum().alias("imageCount"),
                pl.col("image_count")
                .filter(pl.col("imputed"))
                .sum()
                .alias("imputedImageCount"),
            )
            .sort(["imageCount", "species"], descending=[True, False])
        )
        return {
            "countryCode": code,
            "countryName": self.lookup.country_name(code),
            "species": species.to_dicts(),
        }
