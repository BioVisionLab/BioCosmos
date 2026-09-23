"""Institution code -> full name and website.

Read by the provider table, and by the image metadata panels to name the
specimen holder.

gbif_meta records who holds a specimen only as `institutionCode`, an
abbreviation that is not even unique ("TU" is four institutions in GRSciColl,
none of them the University of Tartu that publishes this data under it).
instharmonize resolves each code in the context of the datasets it appears in,
against the public GBIF registries, and this service keeps the answers in
DuckDB.

Resolution needs the network, so it is incremental: only codes missing from
the table are looked up, and a code that failed on a registry error is simply
left out, to be tried again at the next start. A change to the resolver's
rules or to the overrides changes its fingerprint, which clears the table.
"""

import logging
from pathlib import Path

import duckdb
from harmonize_core.errors import HarmonizeError
from instharmonize import Institution, InstitutionResolver
from instharmonize.overrides import load_overrides
from instharmonize.sources import GBIF_COLUMNS, holder_code_sql, read_records

from ..configs.config import GbifConfig, ImageMetaConfig, InstitutionConfig
from ..database.duckdb import DuckDBClient
from ..database.ingestion_state import IngestionState

logger = logging.getLogger(__name__)

UPDATE_SOURCE_KEY = "institution_directory"

# The columns read back out, in the table's snake_case.
DIRECTORY_COLUMNS = ("code", "name", "homepage", "country", "source")


class InstitutionService:
    """Resolve the collection's institution codes and store them."""

    def __init__(
        self,
        duckdb_client: DuckDBClient,
        resolver: InstitutionResolver | None = None,
    ):
        config = InstitutionConfig()
        self.skip = config.skip
        self.table = config.table
        self.overrides_path = config.overrides_path
        self.image_meta_table = ImageMetaConfig().table
        self.gbif_table = GbifConfig().table
        self.db_client = duckdb_client
        self._resolver = resolver

    @property
    def resolver(self) -> InstitutionResolver:
        if self._resolver is None:
            extra = Path(self.overrides_path) if self.overrides_path else None
            self._resolver = InstitutionResolver(overrides=load_overrides(extra))
        return self._resolver

    def ensure(self) -> int:
        """Resolve codes not yet in the directory; return how many were added.

        Never raises: without the directory the provider table shows bare
        codes, which is how it looked before there was one.
        """
        if self.skip:
            logger.info("Skipping institution directory as per configuration.")
            return 0
        for table in (self.image_meta_table, self.gbif_table):
            if not self.db_client.table_exists(table):
                logger.warning(
                    f"No '{table}' table; institution codes will not be resolved."
                )
                return 0
        try:
            return self._update()
        except (duckdb.Error, HarmonizeError, OSError) as error:
            logger.error(f"Institution directory update failed: {error}")
            return 0

    def _update(self) -> int:
        fingerprint = self.resolver.fingerprint
        state = IngestionState(self.db_client)
        if not state.is_current(UPDATE_SOURCE_KEY, fingerprint):
            logger.info(
                "Institution resolver or overrides changed; resolving all codes."
            )
            self.db_client.execute(f"DROP TABLE IF EXISTS {self.table}")
        self._create_table()

        known = {
            row[0]
            for row in self.db_client.execute(
                f"SELECT code FROM {self.table}"
            ).fetchall()
        }
        pending = [
            record
            for record in self._records()
            if record.institution_code.strip() not in known
        ]
        state.mark(UPDATE_SOURCE_KEY, fingerprint)
        if not pending:
            logger.info(f"Institution directory is current ({len(known):,} codes).")
            return 0

        codes = {record.institution_code.strip() for record in pending}
        logger.info(f"Resolving {len(codes):,} institution codes against GBIF...")
        resolved = self.resolver.resolve_all(pending)
        stored = [
            institution for institution in resolved.values() if not institution.retry
        ]
        self._insert(stored)

        named = sum(1 for institution in stored if institution.resolved)
        logger.info(
            f"Institution directory: {named:,} of {len(stored):,} new codes named."
        )
        retry = sorted(i.code for i in resolved.values() if i.retry)
        if retry:
            logger.warning(
                "GBIF registry unreachable for "
                f"{', '.join(retry)}; they will be retried at the next start."
            )
        return len(stored)

    def _create_table(self) -> None:
        self.db_client.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.table} (
                code VARCHAR PRIMARY KEY,
                name VARCHAR,
                homepage VARCHAR,
                country VARCHAR,
                grscicoll_key VARCHAR,
                source VARCHAR,
                resolved_at TIMESTAMP
            )
            """
        )

    def _records(self):
        """One record per (code, dataset) behind the collection's images.

        Joined and deduplicated exactly as ImageMetaStats.get_institution_counts
        groups its counts, so every code the provider table lists is here.
        """
        columns = [
            column
            for column in GBIF_COLUMNS.values()
            if self.db_client.column_exists(self.gbif_table, column)
        ]
        selected = ", ".join(f'd."{column}"' for column in columns)
        holder = holder_code_sql(
            '"institutionCode"',
            '"institutionID"' if "institutionID" in columns else None,
        )
        relation = f"""(
            WITH deduped AS (
                SELECT * FROM {self.gbif_table}
                WHERE nullif(trim("occurrenceID"), '') IS NOT NULL
                QUALIFY row_number() OVER (
                    PARTITION BY "occurrenceID"
                    ORDER BY ({holder} IS NULL), "gbifID"
                ) = 1
            )
            SELECT {selected}
            FROM {self.image_meta_table} AS im
            JOIN deduped AS d ON d."occurrenceID" = nullif(trim(im.uuid), '')
        )"""
        return read_records(self.db_client, relation, columns)

    def _insert(self, institutions: list[Institution]) -> None:
        if not institutions:
            return
        with self.db_client.lock:
            self.db_client.conn.executemany(
                f"""
                INSERT OR REPLACE INTO {self.table}
                    (code, name, homepage, country, grscicoll_key, source, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, current_timestamp)
                """,
                [
                    [
                        institution.code,
                        institution.name,
                        institution.homepage,
                        institution.country,
                        institution.grscicoll_key,
                        str(institution.source),
                    ]
                    for institution in institutions
                ],
            )


class InstitutionDirectory:
    """Read the resolved names; absent table reads as an empty directory."""

    def __init__(self, duckdb_client: DuckDBClient):
        self.table = InstitutionConfig().table
        self.db_client = duckdb_client

    def get(self, code: str | None) -> dict | None:
        """One resolved code, in the shape `get_all` returns; None if unnamed."""
        code = (code or "").strip()
        if not code or not self.db_client.table_exists(self.table):
            return None
        try:
            rows = self.db_client.execute_prepared(
                f"""
                SELECT name, homepage, country, source
                FROM {self.table}
                WHERE code = ? AND name IS NOT NULL
                """,
                [code],
            ).fetchall()
        except duckdb.Error as error:
            logger.error(f"Cannot read '{self.table}': {error}")
            return None
        if not rows:
            return None
        name, homepage, country, source = rows[0]
        return {
            "name": name,
            "homepage": homepage,
            "country": country,
            "source": source,
        }

    def get_all(self) -> dict[str, dict]:
        """Every resolved code, as {code: {name, homepage, country, source}}.

        Unresolved codes are left out: a missing entry and an unnamed one mean
        the same thing to a reader, which shows the code alone.
        """
        if not self.db_client.table_exists(self.table):
            return {}
        try:
            rows = self.db_client.execute(
                f"""
                SELECT {", ".join(DIRECTORY_COLUMNS)}
                FROM {self.table}
                WHERE name IS NOT NULL
                """
            ).fetchall()
        except duckdb.Error as error:
            # The names are decoration on the counts; never fail the stats.
            logger.error(f"Cannot read '{self.table}': {error}")
            return {}
        return {
            code: {
                "name": name,
                "homepage": homepage,
                "country": country,
                "source": source,
            }
            for code, name, homepage, country, source in rows
        }
