"""Validated models for coordinate validation against GADM geography."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from harmonize_core.models import ArtifactDigest, FrozenModel, ProjectConfigBase
from pydantic import Field, field_validator, model_validator


class CoordinateColumnMappings(FrozenModel):
    """Map logical georeference fields to source-table columns."""

    source_id: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    country: str | None = None
    adm1: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_to_none(cls, value: object) -> object:
        return None if value == "" else value

    def as_logical_dict(self) -> dict[str, str]:
        return {key: value for key, value in self.model_dump().items() if value is not None}


class CoordinateValidationConfig(FrozenModel):
    """Control tiled loading of administrative reference geometries."""

    tile_size: float = Field(default=5.0, gt=0, le=180)
    tile_buffer: float = Field(default=0.001, ge=0, le=5)


class CoordinateRunConfig(FrozenModel):
    """Hold optional coordinate-validation settings from TOML or the CLI."""

    db: Path | None = None
    table: str | None = None
    gadm: Path | None = None
    output: Path | None = None
    reports_dir: Path | None = None
    gadm_layer: str | None = None
    tile_size: float = Field(default=5.0, gt=0, le=180)
    tile_buffer: float = Field(default=0.001, ge=0, le=5)
    force: bool = False


class EffectiveCoordinateRunConfig(FrozenModel):
    """Represent fully resolved settings for one coordinate-validation run."""

    db: Path
    table: str
    gadm: Path
    output: Path
    columns: CoordinateColumnMappings
    gadm_layer: str | None = None
    tile_size: float = Field(default=5.0, gt=0, le=180)
    tile_buffer: float = Field(default=0.001, ge=0, le=5)
    force: bool = False

    @model_validator(mode="after")
    def sources_must_exist(self) -> EffectiveCoordinateRunConfig:
        if not self.db.is_file():
            raise ValueError(f"Occurrence database does not exist: {self.db}")
        if not self.gadm.is_file():
            raise ValueError(f"GADM GeoPackage does not exist: {self.gadm}")
        return self


class GadmSourceInfo(FrozenModel):
    """Describe the selected GADM GeoPackage feature layer."""

    path: Path
    fingerprint: str
    layer: str
    geometry_column: str
    feature_id_column: str
    gid0_column: str
    country_column: str
    gid1_column: str
    adm1_column: str
    srs_id: int


class CoordinateCheck(StrEnum):
    """Classify parsing and geographic-range checks for a coordinate pair."""

    MISSING_COORDINATE = "MISSING_COORDINATE"
    LATITUDE_OUT_OF_RANGE = "LATITUDE_OUT_OF_RANGE"
    LONGITUDE_OUT_OF_RANGE = "LONGITUDE_OUT_OF_RANGE"
    ZERO_COORDINATE = "ZERO_COORDINATE"
    VALID_COORDINATE = "VALID_COORDINATE"

    @property
    def description(self) -> str:
        """Explain the basic coordinate check."""
        descriptions = {
            CoordinateCheck.MISSING_COORDINATE: (
                "Latitude or longitude was missing, non-finite, or could not be parsed."
            ),
            CoordinateCheck.LATITUDE_OUT_OF_RANGE: "Latitude was outside -90 to 90 degrees.",
            CoordinateCheck.LONGITUDE_OUT_OF_RANGE: "Longitude was outside -180 to 180 degrees.",
            CoordinateCheck.ZERO_COORDINATE: "Both latitude and longitude were zero.",
            CoordinateCheck.VALID_COORDINATE: "Both coordinates were finite and in range.",
        }
        return descriptions[self]


class CountryCheck(StrEnum):
    """Classify agreement between recorded and coordinate-derived countries."""

    COUNTRY_MATCH = "COUNTRY_MATCH"
    COUNTRY_MISMATCH = "COUNTRY_MISMATCH"
    COUNTRY_NOT_PROVIDED = "COUNTRY_NOT_PROVIDED"
    NO_REFERENCE_MATCH = "NO_REFERENCE_MATCH"
    AMBIGUOUS_REFERENCE = "AMBIGUOUS_REFERENCE"
    NOT_EVALUATED = "NOT_EVALUATED"

    @property
    def description(self) -> str:
        """Explain the country comparison result."""
        descriptions = {
            CountryCheck.COUNTRY_MATCH: "Recorded and coordinate-derived countries agree.",
            CountryCheck.COUNTRY_MISMATCH: "Recorded and coordinate-derived countries differ.",
            CountryCheck.COUNTRY_NOT_PROVIDED: "No recorded country was supplied.",
            CountryCheck.NO_REFERENCE_MATCH: "The coordinate intersected no reference region.",
            CountryCheck.AMBIGUOUS_REFERENCE: (
                "The coordinate intersected multiple distinct reference regions."
            ),
            CountryCheck.NOT_EVALUATED: "Country was not checked because coordinates were invalid.",
        }
        return descriptions[self]


class Adm1Check(StrEnum):
    """Classify agreement between recorded and coordinate-derived ADM1 values."""

    ADM1_MATCH = "ADM1_MATCH"
    ADM1_MISMATCH = "ADM1_MISMATCH"
    ADM1_NOT_PROVIDED = "ADM1_NOT_PROVIDED"
    NO_ADM1_REFERENCE_MATCH = "NO_ADM1_REFERENCE_MATCH"
    NO_REFERENCE_MATCH = "NO_REFERENCE_MATCH"
    AMBIGUOUS_REFERENCE = "AMBIGUOUS_REFERENCE"
    NOT_EVALUATED = "NOT_EVALUATED"

    @property
    def description(self) -> str:
        """Explain the ADM1 comparison result."""
        descriptions = {
            Adm1Check.ADM1_MATCH: "Recorded and coordinate-derived ADM1 values agree.",
            Adm1Check.ADM1_MISMATCH: "Recorded and coordinate-derived ADM1 values differ.",
            Adm1Check.ADM1_NOT_PROVIDED: "No recorded ADM1 value was supplied.",
            Adm1Check.NO_ADM1_REFERENCE_MATCH: "The reference region had no ADM1 name.",
            Adm1Check.NO_REFERENCE_MATCH: "The coordinate intersected no reference region.",
            Adm1Check.AMBIGUOUS_REFERENCE: (
                "The coordinate intersected multiple distinct reference regions."
            ),
            Adm1Check.NOT_EVALUATED: "ADM1 was not checked because coordinates were invalid.",
        }
        return descriptions[self]


class CoordinateValidationStatus(StrEnum):
    """Classify the final coordinate-validation outcome."""

    MISSING_COORDINATE = "MISSING_COORDINATE"
    COORDINATE_OUT_OF_RANGE = "COORDINATE_OUT_OF_RANGE"
    ZERO_COORDINATE = "ZERO_COORDINATE"
    NO_REFERENCE_MATCH = "NO_REFERENCE_MATCH"
    AMBIGUOUS_REFERENCE = "AMBIGUOUS_REFERENCE"
    COUNTRY_MISMATCH = "COUNTRY_MISMATCH"
    ADM1_MISMATCH = "ADM1_MISMATCH"
    VALID = "VALID"

    @property
    def description(self) -> str:
        """Explain the final validation outcome."""
        descriptions = {
            CoordinateValidationStatus.MISSING_COORDINATE: (
                "Latitude or longitude was missing or invalid."
            ),
            CoordinateValidationStatus.COORDINATE_OUT_OF_RANGE: (
                "Latitude or longitude was outside its valid geographic range."
            ),
            CoordinateValidationStatus.ZERO_COORDINATE: "The coordinate pair was 0,0.",
            CoordinateValidationStatus.NO_REFERENCE_MATCH: (
                "The coordinate intersected no GADM region."
            ),
            CoordinateValidationStatus.AMBIGUOUS_REFERENCE: (
                "The coordinate intersected multiple distinct GADM regions."
            ),
            CoordinateValidationStatus.COUNTRY_MISMATCH: (
                "The recorded country disagreed with the coordinate-derived country."
            ),
            CoordinateValidationStatus.ADM1_MISMATCH: (
                "The recorded ADM1 disagreed with the coordinate-derived ADM1."
            ),
            CoordinateValidationStatus.VALID: ("The coordinate passed all applicable checks."),
        }
        return descriptions[self]


class CoordinateRunManifest(FrozenModel):
    """Record coordinate-validation provenance, outputs, timing, and counts."""

    schema_version: int = 1
    run_id: str
    package_version: str
    started_at: str
    completed_at: str
    runtime_seconds: float
    points_per_second: float | None = None
    occurrence_database: str
    occurrence_table: str
    gadm_source: str
    gadm_sha256: str
    gadm_layer: str
    detected_columns: dict[str, str]
    validation: dict[str, float]
    outputs: dict[str, str]
    artifacts: list[ArtifactDigest] = Field(default_factory=list)
    counts: dict[str, int]


class CoordinateInspectionReport(FrozenModel):
    """Summarize coordinate-column discovery and validation results."""

    database: Path
    table: str
    row_count: int
    distinct_point_count: int
    detected_columns: dict[str, str]
    available_columns: list[str]
    warnings: list[str] = Field(default_factory=list)
    valid: bool = True


class SharedRunConfig(ProjectConfigBase):
    """Read the settings coordinate validation inherits from the ``[run]`` table.

    The ``[run]`` table is owned by ``colharmonize``; its taxonomy-only keys are
    ignored here so both tools can share one configuration file.
    """

    db: Path | None = None
    table: str | None = None
    output: Path | None = None
    reports_dir: Path | None = None


class ProjectConfig(ProjectConfigBase):
    """Represent the coordinate-validation view of the shared configuration file."""

    run: SharedRunConfig = Field(default_factory=SharedRunConfig)
    coordinates: CoordinateRunConfig = Field(default_factory=CoordinateRunConfig)
    coordinate_columns: CoordinateColumnMappings = Field(default_factory=CoordinateColumnMappings)
