"""Validated models for Catalogue of Life taxonomy matching."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from harmonize_core.models import ArtifactDigest, FrozenModel, ProjectConfigBase
from pydantic import Field, field_validator, model_validator


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


class MatchingConfig(FrozenModel):
    """Control candidate generation, scoring, and ambiguity thresholds."""

    top_k: int = Field(default=5, ge=1, le=100)
    short_epithet_length: int = Field(default=5, ge=1, le=20)
    short_epithet_distance: int = Field(default=1, ge=0, le=5)
    long_epithet_distance: int = Field(default=2, ge=0, le=5)
    genus_distance: int = Field(default=2, ge=0, le=5)
    min_genus_similarity: float = Field(default=0.90, ge=0, le=1)
    min_score_margin: int = Field(default=25, ge=0, le=1000)


class RunConfig(FrozenModel):
    """Hold optional run settings supplied through TOML or the CLI."""

    db: Path | None = None
    table: str | None = None
    col: Path | None = None
    output: Path | None = None
    reports_dir: Path | None = None
    cache_dir: Path | None = None
    csv: bool = False
    plot: bool = False
    # Seaborn palette used by optional summary plots.
    plot_palette: str = "Dark2"
    force: bool = False
    write_back_table: str | None = None


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

    schema_version: int = 1
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
    artifacts: list[ArtifactDigest] = Field(default_factory=list)
    counts: dict[str, int]


class ProjectConfig(ProjectConfigBase):
    """Represent the taxonomy-matching view of the shared configuration file."""

    run: RunConfig = Field(default_factory=RunConfig)
    columns: ColumnMappings = Field(default_factory=ColumnMappings)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)
