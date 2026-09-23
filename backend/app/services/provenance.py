"""Per-occurrence institution and specimen identifier.

`image_meta` carries no institution or catalog-number columns; they live on
gbif_meta, joined to it on uuid = occurrenceID -- the same join
`LocalityService` uses for the locality fields. Built as a table of its own
rather than folded into the locality one, because it answers a different
question (who holds the specimen and how they identify it, not where it was
found) and a reader should be able to omit one without the other.
"""

import logging

import duckdb
from instharmonize.sources import holder_code_sql

from ..configs.config import GbifConfig, ImageMetaConfig, ProvenanceConfig
from ..database.duckdb import DuckDBClient
from ..database.ingestion_state import IngestionState
from .locality import _OccurrenceBlockReader

logger = logging.getLogger(__name__)

UPDATE_SOURCE_KEY = "image_meta_provenance"

# Bumped whenever the shape of the provenance table changes, for the same
# reason STATUS_SCHEMA_VERSION and LOCALITY_SCHEMA_VERSION exist: a
# fingerprint describes the *inputs*, not the shape of the output.
PROVENANCE_SCHEMA_VERSION = 2

REQUIRED_PROVENANCE_COLUMNS = ("institution_code", "catalog_number")


class ProvenanceService:
    """Join the occurrence's institution and catalog number out of gbif_meta."""

    def __init__(self, duckdb_client: DuckDBClient):
        config = ProvenanceConfig()
        self.skip = config.skip
        self.table = config.table
        self.image_meta_table = ImageMetaConfig().table
        self.gbif_table = GbifConfig().table
        self.db_client = duckdb_client

    def ensure(self) -> bool:
        """Rebuild if the result is missing or out of date.

        Returns True when the table was rebuilt. Never raises: a failure here
        leaves the API serving occurrences without provenance, and says so.
        """
        if self.skip:
            logger.info("Skipping provenance build as per configuration.")
            return False
        if not self.db_client.table_exists(self.image_meta_table):
            logger.warning(
                f"No '{self.image_meta_table}' table to derive provenance from; "
                "skipping."
            )
            return False
        if not self.db_client.table_exists(self.gbif_table):
            logger.warning(
                f"No '{self.gbif_table}' table, which is where the institution "
                "and catalog fields live; specimens will carry no provenance."
            )
            return False

        fingerprint = self._source_fingerprint()
        state = IngestionState(self.db_client)
        if (
            state.is_current(UPDATE_SOURCE_KEY, fingerprint)
            and self._table_is_current()
        ):
            logger.info("Provenance table is already current; skipping.")
            return False

        try:
            self._build()
        except (duckdb.Error, ValueError, OSError) as error:
            logger.error(f"Provenance build failed: {error}")
            return False

        state.mark(UPDATE_SOURCE_KEY, fingerprint)
        logger.info(
            "Provenance table built; "
            f"{self.count_with_institution():,} occurrences have an institution."
        )
        return True

    def _source_fingerprint(self) -> str:
        """A token that changes when either source table changes.

        Deliberately coarse -- row counts of both inputs, matching
        LocalityService's own fingerprint for the same reason: neither table
        is edited in place, so a row-count change is exactly when a rebuild
        is warranted.
        """
        occurrences = self.db_client.execute(
            f"SELECT count(*) FROM {self.image_meta_table}"
        ).fetchone()[0]
        gbif = self.db_client.execute(
            f"SELECT count(*) FROM {self.gbif_table}"
        ).fetchone()[0]
        return f"{occurrences}:{gbif}:v{PROVENANCE_SCHEMA_VERSION}"

    def _table_is_current(self) -> bool:
        """Whether a usable table is loaded -- present, and the right shape."""
        if not self.db_client.table_exists(self.table):
            return False
        stale = [
            column
            for column in REQUIRED_PROVENANCE_COLUMNS
            if not self.db_client.column_exists(self.table, column)
        ]
        if stale:
            logger.info(
                f"'{self.table}' is missing {', '.join(stale)}; "
                "rebuilding the provenance table."
            )
            return False
        return True

    def _build(self) -> None:
        # The same holder the provider table counts, so a panel's code always
        # has a row in the institution directory.
        holder = holder_code_sql(
            'gbif."institutionCode"',
            'gbif."institutionID"'
            if self.db_client.column_exists(self.gbif_table, "institutionID")
            else None,
        )
        self.db_client.execute(
            f"""
            CREATE OR REPLACE TABLE {self.table} AS
            WITH cleaned AS (
                SELECT
                    nullif(trim(gbif."occurrenceID"), '') AS occurrence_id,
                    gbif."gbifID" AS gbif_id,
                    {holder} AS institution_code,
                    nullif(trim(gbif."catalogNumber"), '') AS catalog_number
                FROM {self.gbif_table} AS gbif
                WHERE nullif(trim(gbif."occurrenceID"), '') IS NOT NULL
            ),
            -- gbif_meta holds duplicate occurrenceID values (see
            -- LocalityService); the most complete row wins, tie-broken by
            -- gbifID so the choice is stable across rebuilds.
            deduped AS (
                SELECT * FROM cleaned
                QUALIFY row_number() OVER (
                    PARTITION BY occurrence_id
                    ORDER BY (institution_code IS NULL),
                             (catalog_number IS NULL),
                             gbif_id
                ) = 1
            )
            SELECT
                occurrence.img_id,
                deduped.occurrence_id,
                deduped.institution_code,
                deduped.catalog_number
            FROM {self.image_meta_table} AS occurrence
            LEFT JOIN deduped
                   ON deduped.occurrence_id = nullif(trim(occurrence.uuid), '')
            """
        )
        self.db_client.execute(
            f"CREATE INDEX IF NOT EXISTS image_meta_provenance_img_idx "
            f"ON {self.table} (img_id)"
        )
        self._verify_row_count()

    def _verify_row_count(self) -> None:
        """Warn if the join changed the number of occurrence rows.

        A fan-out means one image matched several GBIF records, which would
        duplicate it in search results.
        """
        row = self.db_client.execute(
            f"""
            SELECT
                (SELECT count(*) FROM {self.image_meta_table}) AS occurrences,
                (SELECT count(*) FROM {self.table}) AS provenance
            """
        ).fetchone()
        if row is not None and row[0] != row[1]:
            logger.warning(
                f"Provenance table has {row[1]:,} rows for {row[0]:,} occurrences; "
                "the GBIF join is not one-to-one."
            )

    def count_with_institution(self) -> int:
        row = self.db_client.execute(
            f"SELECT count(*) FROM {self.table} WHERE institution_code IS NOT NULL"
        ).fetchone()
        return row[0] if row is not None else 0


# Read back per occurrence. Snake_case in the table, camelCase out, matching
# every other optional block the metadata panel renders.
_PROVENANCE_FIELDS = (
    ("institution_code", "institutionCode"),
    ("catalog_number", "catalogNumber"),
)


class OccurrenceProvenance:
    """Read the institution and specimen identifier for one occurrence image.

    The table is optional, exactly like `OccurrenceLocality` and
    `OccurrenceCoordinates`: absent until `ProvenanceService.ensure()` has
    built it, and every method degrades to None rather than raising.
    """

    def __init__(self, duckdb_client: DuckDBClient):
        self._reader = _OccurrenceBlockReader(
            duckdb_client, ProvenanceConfig().table, _PROVENANCE_FIELDS
        )

    def get_for_image(self, img_id: str) -> dict | None:
        return self._reader.get_for_image(img_id)
