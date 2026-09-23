"""Command-line interface for instharmonize."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Annotated

import duckdb
import typer
from harmonize_core.errors import HarmonizeError, SourceValidationError

from instharmonize.gbif import DEFAULT_API_URL, GbifRegistry
from instharmonize.models import Institution, InstitutionRecord
from instharmonize.overrides import load_overrides
from instharmonize.resolver import InstitutionResolver
from instharmonize.sources import read_records

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

OUTPUT_FIELDS = ("code", "name", "homepage", "country", "grscicoll_key", "source")


def _fail(exc: Exception) -> typer.Exit:
    typer.echo(f"Error: {exc}", err=True)
    return typer.Exit(code=2)


def _resolver(overrides: Path | None, api_url: str, workers: int) -> InstitutionResolver:
    return InstitutionResolver(
        registry=GbifRegistry(api_url=api_url),
        overrides=load_overrides(overrides),
        max_workers=workers,
    )


@app.command("lookup")
def lookup_command(
    code: Annotated[str, typer.Argument(help="The institutionCode to resolve.")],
    dataset_key: Annotated[str | None, typer.Option("--dataset-key")] = None,
    institution_id: Annotated[str | None, typer.Option("--institution-id")] = None,
    owner: Annotated[str | None, typer.Option("--owner", help="ownerInstitutionCode")] = None,
    publisher: Annotated[str | None, typer.Option("--publisher")] = None,
    country: Annotated[str | None, typer.Option("--country", help="publishingCountry")] = None,
    overrides: Annotated[Path | None, typer.Option("--overrides")] = None,
    api_url: Annotated[str, typer.Option("--api-url")] = DEFAULT_API_URL,
) -> None:
    """Resolve one code. A --dataset-key makes ambiguous codes resolvable."""
    try:
        record = InstitutionRecord(
            institution_code=code,
            dataset_key=dataset_key,
            institution_id=institution_id,
            owner_institution_code=owner,
            publisher=publisher,
            publishing_country=country,
        )
        institution = _resolver(overrides, api_url, 1).resolve(record)
    except HarmonizeError as exc:
        raise _fail(exc) from exc
    for field in OUTPUT_FIELDS:
        typer.echo(f"{field}: {getattr(institution, field) or ''}")
    if institution.retry:
        typer.echo("The GBIF registry could not be reached; try again.", err=True)
        raise typer.Exit(code=1)


@app.command("resolve")
def resolve_command(
    source: Annotated[
        Path,
        typer.Argument(help="A GBIF occurrence download (TSV), or a DuckDB file with --table."),
    ],
    table: Annotated[
        str | None, typer.Option("--table", help="Read this table from a DuckDB source.")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="CSV path; stdout by default.")
    ] = None,
    overrides: Annotated[Path | None, typer.Option("--overrides")] = None,
    workers: Annotated[int, typer.Option("--workers", min=1, max=32)] = 8,
    api_url: Annotated[str, typer.Option("--api-url")] = DEFAULT_API_URL,
) -> None:
    """Resolve every institution code in a GBIF occurrence source to CSV."""
    try:
        records = _read_source(source, table)
        resolved = _resolver(overrides, api_url, workers).resolve_all(records)
    except (HarmonizeError, duckdb.Error) as exc:
        raise _fail(exc) from exc

    occurrences: dict[str, int] = {}
    for record in records:
        code = record.institution_code.strip()
        occurrences[code] = occurrences.get(code, 0) + record.occurrences
    rows = sorted(resolved.values(), key=lambda i: occurrences.get(i.code, 0), reverse=True)
    _write_csv(rows, occurrences, output)

    named = sum(1 for institution in rows if institution.resolved)
    typer.echo(f"Resolved {named:,} of {len(rows):,} institution codes.", err=True)
    retry = [institution.code for institution in rows if institution.retry]
    if retry:
        typer.echo(f"Registry errors, not resolved: {', '.join(retry)}", err=True)


def _read_source(source: Path, table: str | None) -> list[InstitutionRecord]:
    if not source.exists():
        raise SourceValidationError(f"{source} does not exist")
    if table is not None:
        with duckdb.connect(str(source), read_only=True) as connection:
            columns = [row[0] for row in connection.execute(f"DESCRIBE {table}").fetchall()]
            return read_records(connection, table, columns)
    with duckdb.connect() as connection:
        relation = (
            f"read_csv_auto('{str(source).replace(chr(39), chr(39) * 2)}', "
            "delim='\t', all_varchar=true, quote='')"
        )
        columns = [
            row[0] for row in connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
        ]
        return read_records(connection, relation, columns)


def _write_csv(rows: list[Institution], occurrences: dict[str, int], output: Path | None) -> None:
    handle = output.open("w", newline="", encoding="utf-8") if output else sys.stdout
    try:
        writer = csv.writer(handle)
        writer.writerow([*OUTPUT_FIELDS, "occurrences"])
        for institution in rows:
            writer.writerow(
                [getattr(institution, f) or "" for f in OUTPUT_FIELDS]
                + [occurrences.get(institution.code, 0)]
            )
    finally:
        if output:
            handle.close()
