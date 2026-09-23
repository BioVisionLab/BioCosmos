"""Reading institution records out of GBIF occurrence data in DuckDB."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from harmonize_core.errors import SourceValidationError

from instharmonize.models import InstitutionRecord

# InstitutionRecord field -> the GBIF occurrence download column it reads.
# Only institutionCode is required; a missing column reads as NULL.
GBIF_COLUMNS = {
    "institution_code": "institutionCode",
    "dataset_key": "datasetKey",
    "institution_id": "institutionID",
    "owner_institution_code": "ownerInstitutionCode",
    "publisher": "publisher",
    "publishing_country": "publishingCountry",
}


class _Executes(Protocol):
    def execute(self, query: str) -> Any: ...


def record_query(relation: str, columns: Iterable[str]) -> str:
    """SQL grouping `relation` into one row per InstitutionRecord.

    `relation` is a table name or a parenthesized subquery with the GBIF column
    names; `columns` are the ones it actually has.
    """
    present = set(columns)
    if GBIF_COLUMNS["institution_code"] not in present:
        raise SourceValidationError(f"{relation} has no institutionCode column")
    selects = [
        f"nullif(trim(CAST(\"{column}\" AS VARCHAR)), '') AS {field}"
        if column in present
        else f"CAST(NULL AS VARCHAR) AS {field}"
        for field, column in GBIF_COLUMNS.items()
    ]
    return f"""
        SELECT {", ".join(selects)}, count(*) AS occurrences
        FROM {relation}
        WHERE nullif(trim(CAST("institutionCode" AS VARCHAR)), '') IS NOT NULL
        GROUP BY ALL
    """


def read_records(
    connection: _Executes, relation: str, columns: Iterable[str]
) -> list[InstitutionRecord]:
    """Run `record_query` on any DuckDB connection-like object."""
    rows = connection.execute(record_query(relation, columns)).fetchall()
    fields = [*GBIF_COLUMNS, "occurrences"]
    return [InstitutionRecord(**dict(zip(fields, row, strict=True))) for row in rows]
