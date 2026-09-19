"""Occurrence and Catalogue of Life source adapters."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb

from colharmonize.errors import SourceValidationError
from colharmonize.identifiers import parse_table_identifier, qualified_name, quote_identifier
from colharmonize.models import (
    CatalogColumn,
    CatalogTable,
    ColSourceInfo,
    ColumnMappings,
    CoordinateColumnMappings,
    InspectionReport,
)

STANDARD_COLUMNS: dict[str, tuple[str, ...]] = {
    "genus": ("genus",),
    "specific_epithet": ("specificEpithet", "specific_epithet"),
    "family": ("family",),
    "order": ("order",),
    "class": ("class",),
    "kingdom": ("kingdom",),
    "taxon_rank": ("taxonRank", "taxon_rank"),
    "authorship": ("scientificNameAuthorship", "scientific_name_authorship", "authorship"),
}
NAME_COLUMNS = ("scientificName", "species")
UNSUPPORTED_TYPES = ("BLOB", "STRUCT", "MAP", "LIST", "UNION")
COORDINATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "source_id": ("occurrenceID", "occurrence_id", "id"),
    "latitude": ("decimalLatitude", "decimal_latitude", "latitude", "lat"),
    "longitude": ("decimalLongitude", "decimal_longitude", "longitude", "lon", "lng"),
    "country": ("countryCode", "country_code", "country"),
    "adm1": ("stateProvince", "state_province", "adm1", "state", "province"),
}


class DuckDBCatalog:
    """Read-only table and column discovery for a DuckDB database."""

    def __init__(self, database: Path) -> None:
        self.database = database

    @contextmanager
    def connect(self) -> Iterator[duckdb.DuckDBPyConnection]:
        if not self.database.is_file():
            raise SourceValidationError(f"DuckDB database does not exist: {self.database}")
        connection = duckdb.connect(str(self.database), read_only=True)
        try:
            yield connection
        finally:
            connection.close()

    def list_tables(self) -> list[CatalogTable]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT table_schema, table_name, table_type
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY table_schema, table_name
                """
            ).fetchall()
        return [
            CatalogTable(schema_name=row[0], table_name=row[1], table_type=row[2]) for row in rows
        ]

    def list_columns(self, table: str) -> list[CatalogColumn]:
        identifier = parse_table_identifier(table)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = ? AND table_name = ?
                ORDER BY ordinal_position
                """,
                [identifier.schema_name, identifier.table_name],
            ).fetchall()
        if not rows:
            raise SourceValidationError(f"Table does not exist: {identifier.display_name}")
        return [
            CatalogColumn(name=row[0], data_type=row[1], nullable=row[2] == "YES") for row in rows
        ]


class OccurrenceSource:
    """Read-only access to an occurrence table and its taxonomic columns."""

    def __init__(self, database: Path, table: str) -> None:
        self.database = database
        self.identifier = parse_table_identifier(table)

    @contextmanager
    def connect(self, *, read_only: bool = True) -> Iterator[duckdb.DuckDBPyConnection]:
        if not self.database.is_file():
            raise SourceValidationError(f"Occurrence database does not exist: {self.database}")
        connection = duckdb.connect(str(self.database), read_only=read_only)
        try:
            yield connection
        finally:
            connection.close()

    def columns(self, connection: duckdb.DuckDBPyConnection) -> dict[str, str]:
        rows = connection.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ?
            ORDER BY ordinal_position
            """,
            [self.identifier.schema_name, self.identifier.table_name],
        ).fetchall()
        if not rows:
            raise SourceValidationError(f"Table does not exist: {self.identifier.display_name}")
        return dict(rows)

    def resolve_columns(
        self,
        available: dict[str, str],
        mappings: ColumnMappings,
        *,
        strict: bool = True,
    ) -> tuple[dict[str, str], list[str]]:
        lower_names: dict[str, list[str]] = {}
        for name in available:
            lower_names.setdefault(name.casefold(), []).append(name)

        def resolve(name: str) -> str:
            if name in available:
                return name
            matches = lower_names.get(name.casefold(), [])
            if len(matches) == 1:
                return matches[0]
            raise SourceValidationError(f"Mapped column does not exist or is ambiguous: {name}")

        resolved: dict[str, str] = {}
        warnings: list[str] = []
        explicit = mappings.as_logical_dict()
        for logical, physical in explicit.items():
            resolved[logical] = resolve(physical)

        if "scientific_name" not in resolved:
            name_matches = [
                resolve(name) for name in NAME_COLUMNS if name.casefold() in lower_names
            ]
            name_matches = list(dict.fromkeys(name_matches))
            if len(name_matches) == 1:
                resolved["scientific_name"] = name_matches[0]
            elif len(name_matches) > 1:
                warnings.append(
                    "Both scientificName and species are present; map scientific_name explicitly."
                )

        for logical, candidates in STANDARD_COLUMNS.items():
            if logical in resolved:
                continue
            for candidate in candidates:
                matches = lower_names.get(candidate.casefold(), [])
                if len(matches) == 1:
                    resolved[logical] = matches[0]
                    break

        incompatible = [
            f"{logical}={physical} ({available[physical]})"
            for logical, physical in resolved.items()
            if available[physical].upper().startswith(UNSUPPORTED_TYPES)
        ]
        if incompatible:
            warnings.append("Incompatible taxonomic columns: " + ", ".join(incompatible))

        has_name = "scientific_name" in resolved
        has_parts = "genus" in resolved and "specific_epithet" in resolved
        if not has_name and not has_parts:
            warnings.append(
                "A scientific-name column or both genus and specific epithet are required."
            )

        if strict and warnings:
            raise SourceValidationError(" ".join(warnings))
        return resolved, warnings

    def resolve_coordinate_columns(
        self,
        available: dict[str, str],
        mappings: CoordinateColumnMappings,
        *,
        strict: bool = True,
    ) -> tuple[dict[str, str], list[str]]:
        """Resolve required coordinates and optional locality columns."""
        lower_names: dict[str, list[str]] = {}
        for name in available:
            lower_names.setdefault(name.casefold(), []).append(name)

        def resolve(name: str) -> str:
            if name in available:
                return name
            matches = lower_names.get(name.casefold(), [])
            if len(matches) == 1:
                return matches[0]
            raise SourceValidationError(f"Mapped column does not exist or is ambiguous: {name}")

        resolved = {
            logical: resolve(physical)
            for logical, physical in mappings.as_logical_dict().items()
        }
        for logical, candidates in COORDINATE_COLUMNS.items():
            if logical in resolved:
                continue
            for candidate in candidates:
                matches = lower_names.get(candidate.casefold(), [])
                if len(matches) == 1:
                    resolved[logical] = matches[0]
                    break

        warnings: list[str] = []
        missing = [field for field in ("latitude", "longitude") if field not in resolved]
        if missing:
            warnings.append("Required coordinate columns were not found: " + ", ".join(missing))
        incompatible = [
            f"{logical}={physical} ({available[physical]})"
            for logical, physical in resolved.items()
            if available[physical].upper().startswith(UNSUPPORTED_TYPES)
        ]
        if incompatible:
            warnings.append("Incompatible coordinate columns: " + ", ".join(incompatible))
        if strict and warnings:
            raise SourceValidationError(" ".join(warnings))
        return resolved, warnings

    def inspect(self, mappings: ColumnMappings) -> InspectionReport:
        with self.connect() as connection:
            available = self.columns(connection)
            resolved, warnings = self.resolve_columns(available, mappings, strict=False)
            table = qualified_name(self.identifier)
            row = connection.execute(f"SELECT count(*) FROM {table}").fetchone()
            assert row is not None
            row_count = row[0]
            count_columns = list(resolved.values())
            if not count_columns:
                distinct_count = 0
            else:
                fields = ", ".join(
                    f"{quote_identifier(f'v{index}')} := cast({quote_identifier(name)} AS VARCHAR)"
                    for index, name in enumerate(count_columns)
                )
                distinct_row = connection.execute(
                    f"SELECT count(DISTINCT to_json(struct_pack({fields}))) FROM {table}"
                ).fetchone()
                assert distinct_row is not None
                distinct_count = distinct_row[0]
        return InspectionReport(
            database=self.database,
            table=self.identifier.display_name,
            row_count=row_count,
            distinct_taxon_count=distinct_count,
            detected_columns=resolved,
            available_columns=list(available),
            warnings=warnings,
            valid=not warnings,
        )


class ColSource:
    """Validate and expose a combined ColDP NameUsage file."""

    SUPPORTED_SUFFIXES = {".tsv", ".tab", ".txt", ".csv"}

    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.is_file():
            raise SourceValidationError(f"Catalogue of Life source does not exist: {path}")

    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        with self.path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @contextmanager
    def materialize(self) -> Iterator[ColSourceInfo]:
        fingerprint = self.fingerprint()
        if self.path.suffix.casefold() in self.SUPPORTED_SUFFIXES:
            yield ColSourceInfo(
                source_path=self.path,
                data_path=self.path,
                fingerprint=fingerprint,
                delimiter="," if self.path.suffix.casefold() == ".csv" else "\t",
            )
            return
        if self.path.suffix.casefold() != ".zip":
            raise SourceValidationError(
                "Unsupported CoL input. Expected a ColDP ZIP or NameUsage TSV/TAB/TXT/CSV file."
            )

        with zipfile.ZipFile(self.path) as archive:
            candidates = [
                member
                for member in archive.namelist()
                if Path(member).suffix.casefold() in self.SUPPORTED_SUFFIXES
                and Path(member).stem.casefold().replace("-", "").replace("_", "") == "nameusage"
            ]
            if len(candidates) != 1:
                raise SourceValidationError(
                    "ColDP archive must contain exactly one NameUsage table; "
                    f"found {len(candidates)}."
                )
            member = candidates[0]
            suffix = Path(member).suffix.casefold()
            with tempfile.TemporaryDirectory(prefix="colharmonize-") as directory:
                extracted = Path(directory) / f"NameUsage{suffix}"
                with archive.open(member) as source, extracted.open("wb") as target:
                    shutil.copyfileobj(source, target)
                yield ColSourceInfo(
                    source_path=self.path,
                    data_path=extracted,
                    fingerprint=fingerprint,
                    delimiter="," if suffix == ".csv" else "\t",
                    archive_member=member,
                )
