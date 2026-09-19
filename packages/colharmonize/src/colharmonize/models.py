"""Validated application models."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FrozenModel(BaseModel):
    """Immutable model base that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ColumnMappings(FrozenModel):
    """Map logical taxonomic fields to source-table columns."""

    scientific_name: str | None = None
    genus: str | None = None
    specific_epithet: str | None = None
    infraspecific_epithet: str | None = None
    family: str | None = None
    order_name: str | None = Field(default=None, alias="order")
    class_name: str | None = Field(default=None, alias="class")
    kingdom: str | None = None
    taxon_rank: str | None = None
    authorship: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_to_none(cls, value: object) -> object:
        return None if value == "" else value

    def as_logical_dict(self) -> dict[str, str]:
        return {
            key: value for key, value in self.model_dump(by_alias=True).items() if value is not None
        }


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


class MatchingConfig(FrozenModel):
    """Control candidate generation, scoring, and ambiguity thresholds."""

    top_k: int = Field(default=5, ge=1, le=100)
    short_epithet_length: int = Field(default=5, ge=1, le=20)
    short_epithet_distance: int = Field(default=1, ge=0, le=5)
    long_epithet_distance: int = Field(default=2, ge=0, le=5)
    genus_distance: int = Field(default=2, ge=0, le=5)
    min_genus_similarity: float = Field(default=0.90, ge=0, le=1)
    min_score_margin: int = Field(default=25, ge=0, le=1000)


class CoordinateValidationConfig(FrozenModel):
    """Control tiled loading of administrative reference geometries."""

    tile_size: float = Field(default=5.0, gt=0, le=180)
    tile_buffer: float = Field(default=0.001, ge=0, le=5)


class RunConfig(FrozenModel):
    """Hold optional run settings supplied through TOML or the CLI."""

    db: Path | None = None
    table: str | None = None
    col: Path | None = None
    output: Path | None = None
    cache_dir: Path | None = None
    csv: bool = False
    plot: bool = False
    # Seaborn palette used by optional summary plots.
    plot_palette: str = "Dark2"
    force: bool = False
    write_back_table: str | None = None


class CoordinateRunConfig(FrozenModel):
    """Hold optional coordinate-validation settings from TOML or the CLI."""

    db: Path | None = None
    table: str | None = None
    gadm: Path | None = None
    output: Path | None = None
    gadm_layer: str | None = None
    tile_size: float = Field(default=5.0, gt=0, le=180)
    tile_buffer: float = Field(default=0.001, ge=0, le=5)
    force: bool = False


class ProjectConfig(FrozenModel):
    """Represent the complete user-supplied project configuration."""

    run: RunConfig = Field(default_factory=RunConfig)
    columns: ColumnMappings = Field(default_factory=ColumnMappings)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)
    coordinates: CoordinateRunConfig = Field(default_factory=CoordinateRunConfig)
    coordinate_columns: CoordinateColumnMappings = Field(default_factory=CoordinateColumnMappings)


class EffectiveRunConfig(FrozenModel):
    """Represent fully resolved settings for one matching run."""

    db: Path
    table: str
    col: Path
    output: Path
    cache_dir: Path
    columns: ColumnMappings
    matching: MatchingConfig
    csv: bool = False
    plot: bool = False
    # Seaborn palette used by optional summary plots.
    plot_palette: str = "Dark2"
    force: bool = False
    write_back_table: str | None = None

    @model_validator(mode="after")
    def sources_must_exist(self) -> EffectiveRunConfig:
        if not self.db.is_file():
            raise ValueError(f"Occurrence database does not exist: {self.db}")
        if not self.col.is_file():
            raise ValueError(f"Catalogue of Life source does not exist: {self.col}")
        return self


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


class TableIdentifier(FrozenModel):
    """Identify a DuckDB table by schema and table name."""

    schema_name: str = "main"
    table_name: str

    @property
    def display_name(self) -> str:
        return f"{self.schema_name}.{self.table_name}"


class InspectionReport(FrozenModel):
    """Summarize source-table discovery and validation results."""

    database: Path
    table: str
    row_count: int
    distinct_taxon_count: int
    detected_columns: dict[str, str]
    available_columns: list[str]
    warnings: list[str] = Field(default_factory=list)
    valid: bool = True


class CatalogTable(FrozenModel):
    """Describe a table exposed by the source DuckDB catalog."""

    schema_name: str
    table_name: str
    table_type: str


class CatalogColumn(FrozenModel):
    """Describe a column exposed by the source DuckDB catalog."""

    name: str
    data_type: str
    nullable: bool


class ColSourceInfo(FrozenModel):
    """Describe a materialized Catalogue of Life source file."""

    source_path: Path
    data_path: Path
    fingerprint: str
    delimiter: str
    archive_member: str | None = None


class IndexInfo(FrozenModel):
    """Describe a generated or reused reference index."""

    path: Path
    fingerprint: str
    reused: bool
    usage_count: int
    accepted_count: int


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
            CoordinateValidationStatus.VALID: (
                "The coordinate passed all applicable checks."
            ),
        }
        return descriptions[self]


class UpdateStatus(StrEnum):
    """Classify the final resolution state of an input taxon."""

    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"

    @property
    def description(self) -> str:
        """Explain what the final resolution state means."""
        descriptions = {
            UpdateStatus.MATCHED: "One accepted taxon was resolved with sufficient evidence.",
            UpdateStatus.AMBIGUOUS: (
                "Candidates were found, but the evidence did not identify one accepted taxon."
            ),
            UpdateStatus.UNMATCHED: (
                "No eligible accepted taxon was found, or the input was invalid or unsupported."
            ),
        }
        return descriptions[self]


class MatchMethod(StrEnum):
    """Identify the evidence method used to resolve an input taxon."""

    EXACT_ACCEPTED = "EXACT_ACCEPTED"
    EXACT_SYNONYM = "EXACT_SYNONYM"
    EXACT_CANONICAL = "EXACT_CANONICAL"
    UNIQUE_FAMILY_EPITHET = "UNIQUE_FAMILY_EPITHET"
    SPELLING_GENUS = "SPELLING_GENUS"
    SPELLING_EPITHET = "SPELLING_EPITHET"
    FUZZY_TYPO = "FUZZY_TYPO"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"

    @property
    def description(self) -> str:
        """Explain how the input taxon was resolved or why it was not."""
        descriptions = {
            MatchMethod.EXACT_ACCEPTED: (
                "The normalized input name exactly matched an accepted name usage."
            ),
            MatchMethod.EXACT_SYNONYM: (
                "The normalized input name exactly matched a synonym of the accepted taxon."
            ),
            MatchMethod.EXACT_CANONICAL: (
                "The parsed genus and epithet exactly matched an accepted canonical binomial."
            ),
            MatchMethod.UNIQUE_FAMILY_EPITHET: (
                "One accepted taxon matched the input family and specific epithet."
            ),
            MatchMethod.SPELLING_GENUS: (
                "The family and epithet matched while genus spelling similarity resolved the taxon."
            ),
            MatchMethod.SPELLING_EPITHET: (
                "The family and genus matched while epithet edit distance resolved the taxon."
            ),
            MatchMethod.FUZZY_TYPO: (
                "Family-restricted spelling similarity resolved both genus and epithet."
            ),
            MatchMethod.AMBIGUOUS: (
                "Candidate evidence did not clearly separate one accepted taxon."
            ),
            MatchMethod.UNMATCHED: (
                "No candidate was found, or the input binomial or rank was unsupported."
            ),
        }
        return descriptions[self]


class RunManifest(FrozenModel):
    """Record run provenance, outputs, timing, and result counts."""

    run_id: str
    package_version: str
    started_at: str
    completed_at: str
    runtime_seconds: float
    taxa_per_second: float | None = None
    occurrence_database: str
    occurrence_table: str
    col_source: str
    col_sha256: str
    reference_index: str
    detected_columns: dict[str, str]
    matching: dict[str, int | float]
    outputs: dict[str, str]
    counts: dict[str, int]


class CoordinateRunManifest(FrozenModel):
    """Record coordinate-validation provenance, outputs, timing, and counts."""

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
    counts: dict[str, int]
