"""Reusable Catalogue of Life reference index."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import duckdb

from colharmonize.errors import SourceValidationError
from colharmonize.identifiers import quote_identifier, quote_literal
from colharmonize.models import ColSourceInfo, IndexInfo
from colharmonize.names import subspecies_epithet_sql
from colharmonize.sources import ColSource

INDEX_SCHEMA_VERSION = 2


def _canonical_column(name: str) -> str:
    lowered = name.casefold()
    for prefix in ("col:", "dwc:"):
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix) :]
    return lowered.replace("_", "").replace("-", "")


def _resolve_columns(columns: list[str]) -> dict[str, str | None]:
    normalized: dict[str, list[str]] = {}
    for column in columns:
        normalized.setdefault(_canonical_column(column), []).append(column)

    def one(*names: str, required: bool = False) -> str | None:
        for name in names:
            matches = normalized.get(_canonical_column(name), [])
            if len(matches) == 1:
                return matches[0]
        if required:
            raise SourceValidationError(f"NameUsage is missing required column: {names[0]}")
        return None

    return {
        "id": one("ID", "taxonID", required=True),
        "scientific_name": one("scientificName", required=True),
        "status": one("status", "taxonomicStatus", required=True),
        "parent_id": one("parentID", "acceptedNameUsageID"),
        "rank": one("rank", "taxonRank", required=True),
        "generic_name": one("genericName", "genus"),
        "specific_epithet": one("specificEpithet"),
        "infraspecific_epithet": one("infraspecificEpithet"),
        "family": one("family"),
        "authorship": one("authorship", "scientificNameAuthorship"),
    }


def _column_expr(column: str | None) -> str:
    return "NULL::VARCHAR" if column is None else f"cast({quote_identifier(column)} AS VARCHAR)"


class ReferenceIndex:
    """Build and reuse a compact species, subspecies, and genus CoL index."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir

    def ensure(self, source: ColSource, *, rebuild: bool = False) -> IndexInfo:
        fingerprint = source.fingerprint()
        target_dir = self.cache_dir / fingerprint
        target = target_dir / f"reference-v{INDEX_SCHEMA_VERSION}.duckdb"
        if target.is_file() and not rebuild:
            return self._describe(target, fingerprint, reused=True)

        target_dir.mkdir(parents=True, exist_ok=True)
        temporary = target_dir / f".{target.name}.{uuid.uuid4().hex}.tmp"
        try:
            with source.materialize() as info:
                self._build(temporary, info)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return self._describe(target, fingerprint, reused=False)

    def _describe(self, path: Path, fingerprint: str, *, reused: bool) -> IndexInfo:
        connection = duckdb.connect(str(path), read_only=True)
        try:
            usage_row = connection.execute("SELECT count(*) FROM usage_lookup").fetchone()
            accepted_row = connection.execute("SELECT count(*) FROM accepted_taxa").fetchone()
            assert usage_row is not None and accepted_row is not None
            usage_count = usage_row[0]
            accepted_count = accepted_row[0]
        except duckdb.Error as exc:
            raise SourceValidationError(f"Invalid cached reference index {path}: {exc}") from exc
        finally:
            connection.close()
        return IndexInfo(
            path=path,
            fingerprint=fingerprint,
            reused=reused,
            usage_count=usage_count,
            accepted_count=accepted_count,
        )

    def _build(self, path: Path, info: ColSourceInfo) -> None:
        connection = duckdb.connect(str(path))
        try:
            options = (
                f"delim={quote_literal(info.delimiter)}, header=true, all_varchar=true, "
                "sample_size=-1, null_padding=true"
            )
            if info.delimiter == "\t":
                options += ", quote=''"
            connection.execute(
                f"CREATE TABLE imported_name_usage AS SELECT * FROM read_csv("
                f"{quote_literal(str(info.data_path))}, {options})"
            )
            columns = [
                row[1]
                for row in connection.execute("PRAGMA table_info('imported_name_usage')").fetchall()
            ]
            resolved = _resolve_columns(columns)
            expressions = {key: _column_expr(value) for key, value in resolved.items()}
            infra_sql = subspecies_epithet_sql("replace(usage_name, '_', ' ')", "authorship")
            connection.execute(
                f"""
                CREATE TABLE name_usage AS
                WITH prepared AS (
                    SELECT
                        nullif(trim({expressions["id"]}), '') AS usage_id,
                        nullif(trim({expressions["scientific_name"]}), '') AS usage_name,
                        nullif(trim({expressions["status"]}), '') AS usage_status,
                        nullif(trim({expressions["parent_id"]}), '') AS parent_id,
                        lower(nullif(trim({expressions["rank"]}), '')) AS taxon_rank,
                        nullif(trim({expressions["generic_name"]}), '') AS structured_genus,
                        nullif(trim({expressions["specific_epithet"]}), '') AS structured_epithet,
                        nullif(trim({expressions["infraspecific_epithet"]}), '')
                            AS structured_infraspecific_epithet,
                        nullif(trim({expressions["family"]}), '') AS family,
                        nullif(trim({expressions["authorship"]}), '') AS authorship,
                        lower(regexp_replace(trim({expressions["scientific_name"]}),
                            '[_\\s]+', ' ', 'g')) AS usage_name_norm
                    FROM imported_name_usage
                ), parsed AS (
                    SELECT *,
                        lower(coalesce(structured_genus,
                            regexp_extract(
                                regexp_replace(usage_name_norm, '\\s*\\([^)]+\\)\\s*', ' ', 'g'),
                                '^\\s*([^ ]+)', 1))) AS genus_norm,
                        lower(coalesce(structured_epithet,
                            regexp_extract(
                                regexp_replace(usage_name_norm, '\\s*\\([^)]+\\)\\s*', ' ', 'g'),
                                '^\\s*[^ ]+\\s+([^ ]+)', 1))) AS epithet_norm,
                        lower(coalesce(structured_infraspecific_epithet, {infra_sql}))
                            AS infraspecific_epithet_norm,
                        lower(family) AS family_norm,
                        lower(regexp_replace(trim(authorship), '\\s+', ' ', 'g')) AS authorship_norm
                    FROM prepared
                )
                SELECT *, CASE taxon_rank
                    WHEN 'genus' THEN genus_norm
                    WHEN 'subspecies' THEN concat_ws(' ', genus_norm, epithet_norm,
                                                    infraspecific_epithet_norm)
                    ELSE concat(genus_norm, ' ', epithet_norm) END AS canonical_key
                FROM parsed
                WHERE usage_id IS NOT NULL
                  AND usage_name IS NOT NULL
                  AND taxon_rank IN ('species', 'subspecies', 'genus')
                  AND genus_norm <> ''
                  AND (taxon_rank = 'genus' OR epithet_norm <> '')
                  AND (taxon_rank <> 'subspecies' OR infraspecific_epithet_norm IS NOT NULL)
                """
            )
            connection.execute(
                """
                CREATE TABLE accepted_taxa AS
                SELECT
                    usage_id AS accepted_id,
                    usage_name AS accepted_name,
                    authorship AS accepted_authorship,
                    genus_norm AS accepted_genus,
                    CASE WHEN taxon_rank <> 'genus' THEN epithet_norm END AS accepted_epithet,
                    infraspecific_epithet_norm AS accepted_infraspecific_epithet,
                    family AS accepted_family,
                    family_norm,
                    taxon_rank,
                    usage_status AS accepted_status,
                    usage_name_norm,
                    authorship_norm,
                    canonical_key
                FROM name_usage
                WHERE lower(usage_status) IN ('accepted', 'provisionally accepted')
                """
            )
            connection.execute(
                """
                CREATE TABLE usage_lookup AS
                SELECT
                    usage.usage_id,
                    usage.usage_name,
                    usage.authorship AS usage_authorship,
                    usage.usage_status,
                    usage.genus_norm AS usage_genus,
                    usage.epithet_norm AS usage_epithet,
                    usage.infraspecific_epithet_norm AS usage_infraspecific_epithet,
                    usage.taxon_rank AS usage_rank,
                    usage.usage_name_norm,
                    usage.authorship_norm AS usage_authorship_norm,
                    usage.canonical_key AS usage_canonical_key,
                    accepted.*
                FROM name_usage AS usage
                JOIN accepted_taxa AS accepted
                  ON accepted.accepted_id = CASE
                      WHEN lower(usage.usage_status) IN ('accepted', 'provisionally accepted')
                      THEN usage.usage_id ELSE usage.parent_id END
                """
            )
            connection.execute(
                """
                CREATE TABLE index_metadata AS
                SELECT
                    ?::INTEGER AS schema_version,
                    ?::VARCHAR AS source_sha256,
                    ?::VARCHAR AS source_path,
                    ?::VARCHAR AS archive_member,
                    current_timestamp AS created_at
                """,
                [
                    INDEX_SCHEMA_VERSION,
                    info.fingerprint,
                    str(info.source_path),
                    info.archive_member,
                ],
            )
            connection.execute("CREATE INDEX usage_name_idx ON usage_lookup(usage_name_norm)")
            connection.execute(
                "CREATE INDEX usage_canonical_idx ON usage_lookup(usage_canonical_key)"
            )
            connection.execute(
                "CREATE INDEX accepted_canonical_idx ON accepted_taxa(canonical_key)"
            )
            connection.execute(
                "CREATE INDEX accepted_family_epithet_idx "
                "ON accepted_taxa(family_norm, accepted_epithet)"
            )
            connection.execute(
                "CREATE INDEX accepted_subspecies_idx "
                "ON accepted_taxa(family_norm, accepted_infraspecific_epithet)"
            )
            connection.execute(
                "CREATE INDEX usage_genus_idx ON usage_lookup(usage_rank, usage_genus)"
            )
            connection.execute("DROP TABLE imported_name_usage")
            connection.execute("CHECKPOINT")
        except duckdb.Error as exc:
            raise SourceValidationError(f"Could not build CoL reference index: {exc}") from exc
        finally:
            connection.close()
