"""Coordinate parsing, spatial lookup, and locality-validation pipeline."""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext

import duckdb
import pycountry
from harmonize_core.identifiers import qualified_name, quote_identifier, quote_literal
from harmonize_core.sources import OccurrenceSource
from shapely.geometry import Point

from geoharmonize.geography import GadmFeature, GadmSource
from geoharmonize.models import CoordinateValidationConfig, GadmSourceInfo

_ADMIN_WORDS = re.compile(
    r"\b(?:state|province|region|department|district|county|territory|governorate|prefecture|"
    r"oblast|municipality)\b",
    re.IGNORECASE,
)
_COUNTRY_ALIASES = {
    "bolivia": "BOL",
    "brunei": "BRN",
    "czechia": "CZE",
    "iran": "IRN",
    "laos": "LAO",
    "moldova": "MDA",
    "north korea": "PRK",
    "russia": "RUS",
    "south korea": "KOR",
    "syria": "SYR",
    "taiwan": "TWN",
    "tanzania": "TZA",
    "uk": "GBR",
    "united states": "USA",
    "usa": "USA",
    "venezuela": "VEN",
    "vietnam": "VNM",
}


def _strip_accents(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )


def normalize_geographic_name(value: str | None) -> str | None:
    """Normalize a geographic name for punctuation-insensitive comparison."""
    if value is None or not value.strip():
        return None
    return re.sub(r"[^a-z0-9]+", "", _strip_accents(value).casefold()) or None


def normalize_adm1(value: str | None) -> str | None:
    """Normalize ADM1 names while removing generic administrative words."""
    if value is None or not value.strip():
        return None
    without_admin_words = _ADMIN_WORDS.sub(" ", _strip_accents(value).casefold())
    return re.sub(r"[^a-z0-9]+", "", without_admin_words) or None


def resolve_country_code(value: str | None) -> str | None:
    """Resolve country names and alpha-2/alpha-3 codes to ISO alpha-3."""
    if value is None or not value.strip():
        return None
    cleaned = re.sub(r"\s+", " ", value.strip()).casefold()
    if cleaned in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[cleaned]
    try:
        return str(pycountry.countries.lookup(value.strip()).alpha_3)
    except LookupError:
        return None


class CoordinateValidationPipeline:
    """Validate occurrence coordinates against a tiled GADM ADM1 subset."""

    def __init__(
        self,
        connection: duckdb.DuckDBPyConnection,
        occurrence: OccurrenceSource,
        resolved_columns: dict[str, str],
        gadm: GadmSource,
        gadm_info: GadmSourceInfo,
        validation: CoordinateValidationConfig,
    ) -> None:
        self.connection = connection
        self.occurrence = occurrence
        self.columns = resolved_columns
        self.gadm = gadm
        self.gadm_info = gadm_info
        self.validation = validation
        self.features: list[GadmFeature] = []
        self._register_functions()

    def run(
        self,
        stage: Callable[[str], AbstractContextManager[None]] | None = None,
    ) -> None:
        """Run all coordinate stages, optionally reporting long operations."""
        report = stage or (lambda _label: nullcontext())
        operations = (
            ("Attach occurrence data", self._attach_source),
            ("Parse and validate coordinate values", self._extract_inputs),
            ("Load GADM polygons for occupied tiles", self._load_reference_subset),
            ("Intersect coordinates with GADM polygons", self._match_points),
            ("Resolve coordinate validation statuses", self._create_validation),
        )
        for label, operation in operations:
            with report(label):
                operation()

    def refresh_metrics(self) -> None:
        """Create compact counts for each validation component."""
        self.connection.execute("DROP TABLE IF EXISTS coordinate_summary_metrics")
        self.connection.execute(
            """
            CREATE TABLE coordinate_summary_metrics AS
            SELECT 'validation_status' AS metric_group, validation_status AS metric_value,
                   count(*)::BIGINT AS record_count
            FROM coordinate_validation GROUP BY validation_status
            UNION ALL
            SELECT 'coordinate_check', coordinate_check, count(*)::BIGINT
            FROM coordinate_validation GROUP BY coordinate_check
            UNION ALL
            SELECT 'country_check', country_check, count(*)::BIGINT
            FROM coordinate_validation GROUP BY country_check
            UNION ALL
            SELECT 'adm1_check', adm1_check, count(*)::BIGINT
            FROM coordinate_validation GROUP BY adm1_check
            ORDER BY metric_group, metric_value
            """
        )

    def _register_functions(self) -> None:
        self.connection.create_function(
            "normalize_geographic_name",
            normalize_geographic_name,
            ["VARCHAR"],
            "VARCHAR",
        )
        self.connection.create_function(
            "normalize_adm1",
            normalize_adm1,
            ["VARCHAR"],
            "VARCHAR",
        )
        self.connection.create_function(
            "resolve_country_code",
            resolve_country_code,
            ["VARCHAR"],
            "VARCHAR",
        )

    def _attach_source(self) -> None:
        self.connection.execute(
            f"ATTACH {quote_literal(str(self.occurrence.database))} "
            "AS occurrence_source (READ_ONLY)"
        )

    def _source_expr(self, logical: str) -> str:
        physical = self.columns.get(logical)
        if physical is None:
            return "NULL::VARCHAR"
        return f"cast({quote_identifier(physical)} AS VARCHAR)"

    def _extract_inputs(self) -> None:
        source_table = (
            f"{quote_identifier('occurrence_source')}.{qualified_name(self.occurrence.identifier)}"
        )
        self.connection.execute(
            f"""
            CREATE TABLE coordinate_input_rows AS
            WITH raw AS (
                SELECT
                    row_number() OVER ()::BIGINT AS source_row_number,
                    {self._source_expr("source_id")} AS source_id,
                    {self._source_expr("latitude")} AS original_latitude,
                    {self._source_expr("longitude")} AS original_longitude,
                    {self._source_expr("country")} AS recorded_country,
                    {self._source_expr("adm1")} AS recorded_adm1
                FROM {source_table}
            ), parsed AS (
                SELECT *,
                    try_cast(nullif(trim(original_latitude), '') AS DOUBLE) AS latitude,
                    try_cast(nullif(trim(original_longitude), '') AS DOUBLE) AS longitude,
                    resolve_country_code(recorded_country) AS recorded_country_code,
                    normalize_geographic_name(recorded_country) AS normalized_country,
                    normalize_adm1(recorded_adm1) AS normalized_adm1
                FROM raw
            ), checked AS (
                SELECT *,
                    CASE
                        WHEN latitude IS NULL OR longitude IS NULL
                             OR NOT isfinite(latitude) OR NOT isfinite(longitude)
                        THEN 'MISSING_COORDINATE'
                        WHEN latitude < -90 OR latitude > 90 THEN 'LATITUDE_OUT_OF_RANGE'
                        WHEN longitude < -180 OR longitude > 180 THEN 'LONGITUDE_OUT_OF_RANGE'
                        WHEN latitude = 0 AND longitude = 0 THEN 'ZERO_COORDINATE'
                        ELSE 'VALID_COORDINATE'
                    END AS coordinate_check
                FROM parsed
            )
            SELECT *,
                CASE WHEN coordinate_check = 'VALID_COORDINATE'
                     THEN sha256(to_json(struct_pack(
                         latitude := latitude,
                         longitude := longitude
                     ))) END AS point_key
            FROM checked
            """
        )
        self.connection.execute(
            """
            CREATE TABLE coordinate_points AS
            SELECT point_key, min(latitude) AS latitude, min(longitude) AS longitude,
                   count(*)::BIGINT AS occurrence_count
            FROM coordinate_input_rows
            WHERE point_key IS NOT NULL
            GROUP BY point_key
            ORDER BY point_key
            """
        )

    def _load_reference_subset(self) -> None:
        point_rows = self.connection.execute(
            "SELECT latitude, longitude FROM coordinate_points"
        ).fetchall()
        size = self.validation.tile_size
        occupied_tiles = {
            (math.floor(float(longitude) / size) * size, math.floor(float(latitude) / size) * size)
            for latitude, longitude in point_rows
        }
        tile_bounds = sorted((x, y, x + size, y + size) for x, y in occupied_tiles)
        self.features = self.gadm.load_features(
            self.gadm_info,
            tile_bounds,
            buffer=self.validation.tile_buffer,
        )
        self.connection.execute(
            """
            CREATE TABLE coordinate_reference_subset(
                feature_id VARCHAR PRIMARY KEY,
                gid_0 VARCHAR,
                country VARCHAR,
                gid_1 VARCHAR,
                adm1 VARCHAR,
                geometry BLOB,
                min_x DOUBLE,
                max_x DOUBLE,
                min_y DOUBLE,
                max_y DOUBLE
            )
            """
        )
        if self.features:
            self.connection.executemany(
                "INSERT INTO coordinate_reference_subset VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        feature.feature_id,
                        feature.gid0,
                        feature.country,
                        feature.gid1,
                        feature.adm1,
                        feature.geometry_blob,
                        feature.min_x,
                        feature.max_x,
                        feature.min_y,
                        feature.max_y,
                    )
                    for feature in self.features
                ],
            )

    def _match_points(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE coordinate_reference_candidates(
                point_key VARCHAR,
                feature_id VARCHAR,
                gid_0 VARCHAR,
                country VARCHAR,
                gid_1 VARCHAR,
                adm1 VARCHAR,
                PRIMARY KEY(point_key, gid_0, gid_1)
            )
            """
        )
        candidates: list[tuple[str, str, str, str, str, str]] = []
        point_rows = self.connection.execute(
            "SELECT point_key, latitude, longitude FROM coordinate_points"
        ).fetchall()
        ordered_features = sorted(self.features, key=lambda feature: feature.feature_id)
        for point_key, latitude, longitude in point_rows:
            x = float(longitude)
            y = float(latitude)
            point = Point(x, y)
            regions: dict[tuple[str, str], GadmFeature] = {}
            for feature in ordered_features:
                if not (
                    feature.min_x <= x <= feature.max_x and feature.min_y <= y <= feature.max_y
                ):
                    continue
                if feature.geometry.intersects(point):
                    regions.setdefault((feature.gid0, feature.gid1), feature)
            candidates.extend(
                (
                    str(point_key),
                    feature.feature_id,
                    feature.gid0,
                    feature.country,
                    feature.gid1,
                    feature.adm1,
                )
                for feature in regions.values()
            )
        if candidates:
            self.connection.executemany(
                "INSERT INTO coordinate_reference_candidates VALUES (?, ?, ?, ?, ?, ?)",
                candidates,
            )
        self.connection.execute(
            """
            CREATE TABLE coordinate_point_matches AS
            WITH grouped AS (
                SELECT point_key,
                       count(*)::INTEGER AS reference_match_count,
                       min(feature_id) AS feature_id,
                       min(gid_0) AS gid_0,
                       min(country) AS country,
                       min(gid_1) AS gid_1,
                       min(adm1) AS adm1
                FROM coordinate_reference_candidates
                GROUP BY point_key
            )
            SELECT points.point_key, points.latitude, points.longitude,
                   points.occurrence_count,
                   coalesce(grouped.reference_match_count, 0)::INTEGER AS reference_match_count,
                   CASE WHEN grouped.reference_match_count = 1 THEN grouped.feature_id END
                       AS feature_id,
                   CASE WHEN grouped.reference_match_count = 1 THEN grouped.gid_0 END AS gid_0,
                   CASE WHEN grouped.reference_match_count = 1 THEN grouped.country END AS country,
                   CASE WHEN grouped.reference_match_count = 1 THEN grouped.gid_1 END AS gid_1,
                   CASE WHEN grouped.reference_match_count = 1 THEN grouped.adm1 END AS adm1,
                   CASE
                       WHEN grouped.reference_match_count IS NULL THEN 'NO_REFERENCE_MATCH'
                       WHEN grouped.reference_match_count > 1 THEN 'AMBIGUOUS_REFERENCE'
                       ELSE 'UNIQUE_REFERENCE'
                   END AS reference_status
            FROM coordinate_points AS points
            LEFT JOIN grouped USING (point_key)
            ORDER BY points.point_key
            """
        )

    def _create_validation(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE coordinate_validation AS
            WITH compared AS (
                SELECT inputs.*,
                       matches.reference_match_count,
                       matches.feature_id AS reference_feature_id,
                       matches.gid_0 AS reference_gid_0,
                       matches.country AS reference_country,
                       matches.gid_1 AS reference_gid_1,
                       matches.adm1 AS reference_adm1,
                       matches.reference_status,
                       CASE
                           WHEN inputs.coordinate_check <> 'VALID_COORDINATE'
                           THEN 'NOT_EVALUATED'
                           WHEN matches.reference_match_count = 0 THEN 'NO_REFERENCE_MATCH'
                           WHEN matches.reference_match_count > 1 THEN 'AMBIGUOUS_REFERENCE'
                           WHEN inputs.recorded_country IS NULL
                                OR trim(inputs.recorded_country) = ''
                           THEN 'COUNTRY_NOT_PROVIDED'
                           WHEN inputs.recorded_country_code IS NOT NULL
                                AND upper(inputs.recorded_country_code)
                                    = upper(matches.gid_0)
                           THEN 'COUNTRY_MATCH'
                           WHEN inputs.recorded_country_code IS NULL
                                AND inputs.normalized_country
                                    = normalize_geographic_name(matches.country)
                           THEN 'COUNTRY_MATCH'
                           ELSE 'COUNTRY_MISMATCH'
                       END AS country_check,
                       CASE
                           WHEN inputs.coordinate_check <> 'VALID_COORDINATE'
                           THEN 'NOT_EVALUATED'
                           WHEN matches.reference_match_count = 0 THEN 'NO_REFERENCE_MATCH'
                           WHEN matches.reference_match_count > 1 THEN 'AMBIGUOUS_REFERENCE'
                           WHEN inputs.recorded_adm1 IS NULL OR trim(inputs.recorded_adm1) = ''
                           THEN 'ADM1_NOT_PROVIDED'
                           WHEN matches.adm1 IS NULL OR trim(matches.adm1) = ''
                           THEN 'NO_ADM1_REFERENCE_MATCH'
                           WHEN inputs.normalized_adm1 = normalize_adm1(matches.adm1)
                           THEN 'ADM1_MATCH'
                           ELSE 'ADM1_MISMATCH'
                       END AS adm1_check
                FROM coordinate_input_rows AS inputs
                LEFT JOIN coordinate_point_matches AS matches USING (point_key)
            )
            SELECT *,
                   CASE
                       WHEN coordinate_check = 'MISSING_COORDINATE' THEN 'MISSING_COORDINATE'
                       WHEN coordinate_check IN (
                           'LATITUDE_OUT_OF_RANGE', 'LONGITUDE_OUT_OF_RANGE'
                       ) THEN 'COORDINATE_OUT_OF_RANGE'
                       WHEN coordinate_check = 'ZERO_COORDINATE' THEN 'ZERO_COORDINATE'
                       WHEN reference_match_count = 0 THEN 'NO_REFERENCE_MATCH'
                       WHEN reference_match_count > 1 THEN 'AMBIGUOUS_REFERENCE'
                       WHEN country_check = 'COUNTRY_MISMATCH' THEN 'COUNTRY_MISMATCH'
                       WHEN adm1_check = 'ADM1_MISMATCH' THEN 'ADM1_MISMATCH'
                       ELSE 'VALID'
                   END AS validation_status
            FROM compared
            ORDER BY source_row_number
            """
        )
