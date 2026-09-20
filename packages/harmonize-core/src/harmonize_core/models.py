"""Validated models shared by the harmonize command-line tools."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Immutable model base that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ProjectConfigBase(FrozenModel):
    """Base for per-tool project configuration parsed from a shared TOML file.

    Unknown top-level tables are ignored so that one ``harmonize.toml`` can hold
    the sections of every tool, while each table keeps strict key validation.
    """

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class TableIdentifier(FrozenModel):
    """Identify a DuckDB table by schema and table name."""

    schema_name: str = "main"
    table_name: str

    @property
    def display_name(self) -> str:
        return f"{self.schema_name}.{self.table_name}"


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


class ArtifactDigest(FrozenModel):
    """Record the identity of one produced artifact file.

    The digest is taken after the artifact reaches its final path, so it
    describes the file a consumer will actually read.
    """

    role: str
    path: Path
    bytes: int
    sha256: str
