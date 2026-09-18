"""Validated application models."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ColumnMappings(FrozenModel):
    scientific_name: str | None = None
    genus: str | None = None
    specific_epithet: str | None = None
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
    top_k: int = Field(default=5, ge=1, le=100)
    short_epithet_length: int = Field(default=5, ge=1, le=20)
    short_epithet_distance: int = Field(default=1, ge=0, le=5)
    long_epithet_distance: int = Field(default=2, ge=0, le=5)
    genus_distance: int = Field(default=2, ge=0, le=5)
    min_genus_similarity: float = Field(default=0.90, ge=0, le=1)
    min_score_margin: int = Field(default=25, ge=0, le=1000)


class RunConfig(FrozenModel):
    db: Path | None = None
    table: str | None = None
    col: Path | None = None
    output: Path | None = None
    cache_dir: Path | None = None
    csv: bool = False
    plot: bool = False
    force: bool = False
    write_back_table: str | None = None


class ProjectConfig(FrozenModel):
    run: RunConfig = Field(default_factory=RunConfig)
    columns: ColumnMappings = Field(default_factory=ColumnMappings)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)


class EffectiveRunConfig(FrozenModel):
    db: Path
    table: str
    col: Path
    output: Path
    cache_dir: Path
    columns: ColumnMappings
    matching: MatchingConfig
    csv: bool = False
    plot: bool = False
    force: bool = False
    write_back_table: str | None = None

    @model_validator(mode="after")
    def sources_must_exist(self) -> EffectiveRunConfig:
        if not self.db.is_file():
            raise ValueError(f"Occurrence database does not exist: {self.db}")
        if not self.col.is_file():
            raise ValueError(f"Catalogue of Life source does not exist: {self.col}")
        return self


class TableIdentifier(FrozenModel):
    schema_name: str = "main"
    table_name: str

    @property
    def display_name(self) -> str:
        return f"{self.schema_name}.{self.table_name}"


class InspectionReport(FrozenModel):
    database: Path
    table: str
    row_count: int
    distinct_taxon_count: int
    detected_columns: dict[str, str]
    available_columns: list[str]
    warnings: list[str] = Field(default_factory=list)
    valid: bool = True


class CatalogTable(FrozenModel):
    schema_name: str
    table_name: str
    table_type: str


class CatalogColumn(FrozenModel):
    name: str
    data_type: str
    nullable: bool


class ColSourceInfo(FrozenModel):
    source_path: Path
    data_path: Path
    fingerprint: str
    delimiter: str
    archive_member: str | None = None


class IndexInfo(FrozenModel):
    path: Path
    fingerprint: str
    reused: bool
    usage_count: int
    accepted_count: int


class UpdateStatus(StrEnum):
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"


class MatchMethod(StrEnum):
    EXACT_ACCEPTED = "EXACT_ACCEPTED"
    EXACT_SYNONYM = "EXACT_SYNONYM"
    EXACT_CANONICAL = "EXACT_CANONICAL"
    UNIQUE_FAMILY_EPITHET = "UNIQUE_FAMILY_EPITHET"
    SPELLING_GENUS = "SPELLING_GENUS"
    SPELLING_EPITHET = "SPELLING_EPITHET"
    FUZZY_TYPO = "FUZZY_TYPO"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"


class RunManifest(FrozenModel):
    run_id: str
    package_version: str
    started_at: str
    completed_at: str
    occurrence_database: str
    occurrence_table: str
    col_source: str
    col_sha256: str
    reference_index: str
    detected_columns: dict[str, str]
    matching: dict[str, int | float]
    outputs: dict[str, str]
    counts: dict[str, int]
