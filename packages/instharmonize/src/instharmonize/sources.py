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


# An institutionID that is written out as a name -- two or more words with some
# lowercase, as in split_verbatim_name -- rather than a URI such as a ROR or a
# urn:lsid, which has a scheme and no spaces.
_NAME_LIKE_ID = r"^[^\s:]+\s+\S.*$"


class _Executes(Protocol):
    def execute(self, query: str) -> Any: ...


def holder_code_sql(code_column: str, id_column: str | None = None) -> str:
    """SQL for the code a record's holder is known by.

    `institutionCode` when the record has one. Otherwise `institutionID`, when
    it holds a name rather than an identifier: Naturalis publishes its RMNH
    specimens with an empty institutionCode and "Naturalis Biodiversity Center"
    as the institutionID, and without this they read as having no holder. The
    name then resolves as a verbatim code. A URI there is left alone, since it
    means nothing to a reader shown in place of a code.

    `code_column` and `id_column` are SQL column references, quoted as needed.
    """
    code = f"nullif(trim(CAST({code_column} AS VARCHAR)), '')"
    if id_column is None:
        return code
    identifier = f"trim(CAST({id_column} AS VARCHAR))"
    named = (
        f"CASE WHEN regexp_matches({identifier}, '{_NAME_LIKE_ID}') "
        f"AND regexp_matches({identifier}, '[a-z]') THEN {identifier} END"
    )
    return f"coalesce({code}, {named})"


def record_query(relation: str, columns: Iterable[str]) -> str:
    """SQL grouping `relation` into one row per InstitutionRecord.

    `relation` is a table name or a parenthesized subquery with the GBIF column
    names; `columns` are the ones it actually has.
    """
    present = set(columns)
    if GBIF_COLUMNS["institution_code"] not in present:
        raise SourceValidationError(f"{relation} has no institutionCode column")
    id_column = GBIF_COLUMNS["institution_id"]
    holder = holder_code_sql(
        '"institutionCode"', f'"{id_column}"' if id_column in present else None
    )
    selects = [
        f"{holder} AS {field}"
        if field == "institution_code"
        else f"nullif(trim(CAST(\"{column}\" AS VARCHAR)), '') AS {field}"
        if column in present
        else f"CAST(NULL AS VARCHAR) AS {field}"
        for field, column in GBIF_COLUMNS.items()
    ]
    return f"""
        SELECT {", ".join(selects)}, count(*) AS occurrences
        FROM {relation}
        WHERE {holder} IS NOT NULL
        GROUP BY ALL
    """


def read_records(
    connection: _Executes, relation: str, columns: Iterable[str]
) -> list[InstitutionRecord]:
    """Run `record_query` on any DuckDB connection-like object."""
    rows = connection.execute(record_query(relation, columns)).fetchall()
    fields = [*GBIF_COLUMNS, "occurrences"]
    return [InstitutionRecord(**dict(zip(fields, row, strict=True))) for row in rows]
