"""Read-only DuckDB catalog and occurrence-table adapters."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

import duckdb

from harmonize_core.errors import SourceValidationError
from harmonize_core.identifiers import (
    parse_table_identifier,
    qualified_name,
    quote_identifier,
)
from harmonize_core.models import CatalogColumn, CatalogTable

UNSUPPORTED_TYPES = ("BLOB", "STRUCT", "MAP", "LIST", "UNION")


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
    """Read-only access to an occurrence table.

    Column resolution is domain specific and lives in the tool packages; this
    class owns connection handling, column discovery, and the resolution
    primitives both tools share.
    """

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

    @staticmethod
    def index_by_casefold(available: Mapping[str, str]) -> dict[str, list[str]]:
        """Group the available column names by their case-folded spelling."""
        lower_names: dict[str, list[str]] = {}
        for name in available:
            lower_names.setdefault(name.casefold(), []).append(name)
        return lower_names

    @staticmethod
    def resolve_requested(
        name: str,
        available: Mapping[str, str],
        lower_names: Mapping[str, list[str]],
    ) -> str:
        """Resolve one explicitly mapped column, tolerating case differences."""
        if name in available:
            return name
        matches = lower_names.get(name.casefold(), [])
        if len(matches) == 1:
            return matches[0]
        raise SourceValidationError(f"Mapped column does not exist or is ambiguous: {name}")

    @staticmethod
    def autodetect(
        resolved: dict[str, str],
        aliases: Mapping[str, Sequence[str]],
        lower_names: Mapping[str, list[str]],
    ) -> None:
        """Fill unmapped logical fields from their unambiguous standard aliases."""
        for logical, candidates in aliases.items():
            if logical in resolved:
                continue
            for candidate in candidates:
                matches = lower_names.get(candidate.casefold(), [])
                if len(matches) == 1:
                    resolved[logical] = matches[0]
                    break

    @staticmethod
    def incompatible_columns(
        resolved: Mapping[str, str], available: Mapping[str, str]
    ) -> list[str]:
        """List resolved columns whose DuckDB type cannot be read as text."""
        return [
            f"{logical}={physical} ({available[physical]})"
            for logical, physical in resolved.items()
            if available[physical].upper().startswith(UNSUPPORTED_TYPES)
        ]

    def count_rows_and_combinations(
        self, connection: duckdb.DuckDBPyConnection, columns: Sequence[str]
    ) -> tuple[int, int]:
        """Count table rows and distinct combinations of the given columns."""
        table = qualified_name(self.identifier)
        row = connection.execute(f"SELECT count(*) FROM {table}").fetchone()
        assert row is not None
        row_count = row[0]
        if not columns:
            return row_count, 0
        fields = ", ".join(
            f"{quote_identifier(f'v{index}')} := cast({quote_identifier(name)} AS VARCHAR)"
            for index, name in enumerate(columns)
        )
        distinct_row = connection.execute(
            f"SELECT count(DISTINCT to_json(struct_pack({fields}))) FROM {table}"
        ).fetchone()
        assert distinct_row is not None
        return row_count, distinct_row[0]
