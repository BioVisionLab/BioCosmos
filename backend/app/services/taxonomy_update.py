"""Harmonize occurrence names against Catalogue of Life.

The matching runs in-process, through the `colharmonize` pipeline. It ingests the data to DuckDB
happening at startup unless `col.skip` is set, and once the result is current
it costs nothing.

The pipeline reads its occurrence input from a database file, and DuckDB will
not let a second handle open the one this process already holds, so the taxa
are exported to a small scratch database first.
"""

import logging
import shutil
import tempfile
import time
from pathlib import Path

import duckdb
from colharmonize.index import ReferenceIndex
from colharmonize.models import ColumnMappings, MatchingConfig
from colharmonize.outputs import OutputRepository
from colharmonize.pipeline import MatchPipeline
from colharmonize.sources import ColSource, TaxonOccurrenceSource
from harmonize_core.errors import HarmonizeError

from ..configs.config import ColConfig, ImageMetaConfig
from ..database.duckdb import DuckDBClient
from ..database.ingestion_state import IngestionState, file_fingerprint

logger = logging.getLogger(__name__)

UPDATE_SOURCE_KEY = "col_taxonomy_update"
ATTACH_ALIAS = "taxonomy_update_source"
SCRATCH_TABLE = "occurrence_taxa"

# Tables copied out of the run. input_taxon_variants is not optional: the
# original_* columns on taxonomy_matches are min() aggregates over a taxon's
# variants, so only the variants table can be joined back to occurrence rows.
SOURCE_TABLES = {
    "matches_table": "taxonomy_matches",
    "candidates_table": "taxonomy_candidates",
    "variants_table": "input_taxon_variants",
}

# Occurrence column -> the logical field colharmonize matches it as.
#
# taxon_rank is deliberately absent. image_meta labels 163,895 occurrences
# `subspecies` while carrying a two-word binomial, which the matcher rightly
# rejects as an invalid trinomial; mapping it leaves 26% of the collection
# unmatched, against 5 taxa when the rank cascade decides for itself.
OCCURRENCE_COLUMN_FOR_FIELD = {
    "scientific_name": "species",
    "family": "family",
    "order": "order",
    "class": "class",
    "kingdom": "kingdom",
}

# Logical field -> the column preserving it in input_taxon_variants.
#
# The join must use every mapped field, not the name alone: colharmonize keys
# a taxon on the whole tuple, so two occurrences sharing a name but differing
# in higher taxonomy are separate inputs with separate results.
VARIANT_COLUMN_FOR_FIELD = {
    "scientific_name": "original_scientific_name",
    "genus": "original_genus",
    "specific_epithet": "original_specific_epithet",
    "infraspecific_epithet": "original_infraspecific_epithet",
    "family": "original_family",
    "order": "original_order",
    "class": "original_class",
    "kingdom": "original_kingdom",
    "taxon_rank": "original_taxon_rank",
    "authorship": "original_authorship",
}


class TaxonomyUpdateService:
    """Match the occurrence taxa against CoL and index the result per image."""

    def __init__(self, duckdb_client: DuckDBClient):
        config = ColConfig()
        self.config = config
        self.skip = config.skip
        self.col_path = Path(config.path)
        self.cache_dir = Path(config.cache_dir)
        self.matches_table = config.matches_table
        self.candidates_table = config.candidates_table
        self.variants_table = config.variants_table
        self.status_table = config.occurrence_status_table
        self.image_meta_table = ImageMetaConfig().table
        self.db_client = duckdb_client

    # -- entry point ------------------------------------------------------

    def ensure(self) -> bool:
        """Harmonize if the result is missing or out of date.

        Returns True when the tables were rebuilt.
        """
        if self.skip:
            logger.info("Skipping taxonomy update as per configuration.")
            return False

        release = file_fingerprint(str(self.col_path))
        if release is None:
            logger.warning(
                f"No Catalogue of Life release at '{self.col_path}'; "
                "specimens will carry no taxonomic update."
            )
            return False
        if not self.db_client.table_exists(self.image_meta_table):
            logger.warning(
                f"No '{self.image_meta_table}' table to harmonize; "
                "skipping the taxonomy update."
            )
            return False

        fingerprint = f"{release}|{self._occurrence_fingerprint()}"
        state = IngestionState(self.db_client)
        if state.is_current(UPDATE_SOURCE_KEY, fingerprint) and self._tables_exist():
            logger.info("Taxonomy update is already current; skipping.")
            return False

        started = time.perf_counter()
        try:
            self._harmonize()
        except (HarmonizeError, duckdb.Error, ValueError, OSError) as error:
            logger.error(f"Taxonomy update failed: {error}")
            return False

        state.mark(UPDATE_SOURCE_KEY, fingerprint)
        logger.info(
            f"Taxonomy update built in {time.perf_counter() - started:.1f}s; "
            f"{self.count_by_status()} occurrences classified."
        )
        return True

    def _occurrence_fingerprint(self) -> str:
        """A token that changes when the occurrence taxa change.

        Hashing the distinct taxonomy tuples rather than the whole table, so a
        new image of a known species does not trigger a rematch.
        """
        columns = ", ".join(
            _ident(name) for name in sorted(OCCURRENCE_COLUMN_FOR_FIELD.values())
        )
        row = self.db_client.execute(
            f"""
            SELECT count(*), coalesce(sum(hash(concat_ws('\x1f', {columns}))), 0)
            FROM (SELECT DISTINCT {columns} FROM {self.image_meta_table})
            """
        ).fetchone()
        return f"{row[0]}:{row[1]}"

    # -- the run ----------------------------------------------------------

    def _harmonize(self) -> None:
        """Run the matcher and load its results.

        The scratch directory holds the exported taxa and the pipeline's own
        output database; only the reference index is kept, under `cache_dir`,
        because rebuilding it from the release takes about a minute.
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix="col-harmonize-"))
        try:
            scratch_db = workspace / "occurrences.duckdb"
            self._export_occurrence_taxa(scratch_db)

            occurrence = TaxonOccurrenceSource(scratch_db, SCRATCH_TABLE)
            with occurrence.connect() as source_connection:
                available = occurrence.columns(source_connection)
                resolved, _ = occurrence.resolve_columns(
                    available,
                    ColumnMappings.model_validate(OCCURRENCE_COLUMN_FOR_FIELD),
                    strict=True,
                )

            logger.info("Preparing the Catalogue of Life reference index...")
            index_info = ReferenceIndex(self.cache_dir).ensure(ColSource(self.col_path))
            logger.info(
                f"Reference index {'reused' if index_info.reused else 'built'}: "
                f"{index_info.accepted_count:,} accepted taxa."
            )

            output_dir = workspace / "result"
            repository = OutputRepository(output_dir)
            with repository.build_database(force=True) as connection:
                MatchPipeline(
                    connection,
                    occurrence,
                    resolved,
                    index_info.path,
                    MatchingConfig(),
                ).run()

            self._load_results(repository.database_path)
            self._build_occurrence_status(resolved)
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def _export_occurrence_taxa(self, destination: Path) -> None:
        """Copy the taxonomy columns into a scratch database for the matcher.

        Only these columns, and only as a source of distinct taxa — the
        pipeline groups them itself, and counts occurrences while it does.
        """
        projection = ", ".join(
            _ident(name) for name in OCCURRENCE_COLUMN_FOR_FIELD.values()
        )
        escaped = str(destination).replace("'", "''")
        self.db_client.execute(f"ATTACH '{escaped}' AS {ATTACH_ALIAS}")
        try:
            self.db_client.execute(
                f"CREATE TABLE {ATTACH_ALIAS}.{SCRATCH_TABLE} AS "
                f"SELECT {projection} FROM {self.image_meta_table}"
            )
        finally:
            self.db_client.execute(f"DETACH {ATTACH_ALIAS}")

    def _load_results(self, result_db: Path) -> None:
        """Copy the matcher's tables into the application database."""
        escaped = str(result_db).replace("'", "''")
        self.db_client.execute(f"ATTACH '{escaped}' AS {ATTACH_ALIAS} (READ_ONLY)")
        try:
            for config_key, source_table in SOURCE_TABLES.items():
                destination = getattr(self, config_key)
                self.db_client.execute(
                    f"CREATE OR REPLACE TABLE {destination} AS "
                    f"SELECT * FROM {ATTACH_ALIAS}.{source_table}"
                )
        finally:
            self.db_client.execute(f"DETACH {ATTACH_ALIAS}")

        self.db_client.execute(
            f"CREATE INDEX IF NOT EXISTS col_matches_key_idx "
            f"ON {self.matches_table} (input_taxon_key)"
        )
        self.db_client.execute(
            f"CREATE INDEX IF NOT EXISTS col_candidates_key_idx "
            f"ON {self.candidates_table} (input_taxon_key)"
        )

    def _tables_exist(self) -> bool:
        return not self.db_client.missing_tables(
            [
                self.matches_table,
                self.candidates_table,
                self.variants_table,
                self.status_table,
            ]
        )

    def _build_occurrence_status(self, resolved_columns: dict[str, str]) -> None:
        """Resolve the per-taxon match down to one row per image.

        The join mirrors exactly the fields the matcher keyed its taxa on, so
        it is built from the same resolved mapping the run used rather than a
        fixed list.
        """
        pairs = [
            (occurrence_column, VARIANT_COLUMN_FOR_FIELD[field])
            for field, occurrence_column in sorted(resolved_columns.items())
            if field in VARIANT_COLUMN_FOR_FIELD
        ]
        if not pairs:
            raise ValueError(
                f"Run mapped no usable columns: {sorted(resolved_columns)}"
            )
        logger.info(
            "Joining occurrences on: "
            + ", ".join(f"{occurrence}={variant}" for occurrence, variant in pairs)
        )
        join = "\n              AND ".join(
            f"occurrence.{_ident(occurrence_column)} "
            f"IS NOT DISTINCT FROM variants.{_ident(variant_column)}"
            for occurrence_column, variant_column in pairs
        )
        self.db_client.execute(
            f"""
            CREATE OR REPLACE TABLE {self.status_table} AS
            SELECT
                occurrence.img_id,
                variants.input_taxon_key,
                matches.update_status,
                matches.match_method,
                matches.accepted_id,
                matches.accepted_name,
                matches.accepted_species_name,
                matches.accepted_rank,
                matches.accepted_authorship,
                matches.accepted_family,
                matches.accepted_status,
                matches.match_score,
                matches.score_margin,
                matches.candidate_count,
                matches.genus_changed,
                matches.epithet_changed,
                matches.reason_code,
                -- What the occurrence tables should display in place of the
                -- recorded name: the accepted binomial, else whatever name the
                -- match did resolve to, else nothing. UNMATCHED rows have no
                -- accepted_id at all, so they fall out empty on their own.
                --
                -- accepted_species_name is null for a subspecies whose
                -- binomial CoL does not also accept at species rank, and for
                -- every genus-rank match; in both cases accepted_name still
                -- holds a real accepted name and is worth showing.
                CASE
                    WHEN matches.accepted_species_name IS NOT NULL
                        THEN matches.accepted_species_name
                    ELSE matches.accepted_name
                END AS display_accepted_name
            FROM {self.image_meta_table} AS occurrence
            LEFT JOIN {self.variants_table} AS variants
                   ON {join}
            LEFT JOIN {self.matches_table} AS matches USING (input_taxon_key)
            """
        )
        self.db_client.execute(
            f"CREATE INDEX IF NOT EXISTS image_meta_taxonomy_img_idx "
            f"ON {self.status_table} (img_id)"
        )
        self._verify_row_count()

    def _verify_row_count(self) -> None:
        """Warn if the variant join changed the number of occurrence rows.

        A fan-out means a single image matched several variants, which would
        duplicate it in search results.
        """
        result = self.db_client.execute(
            f"""
            SELECT
                (SELECT count(*) FROM {self.image_meta_table}) AS occurrences,
                (SELECT count(*) FROM {self.status_table}) AS classified
            """
        ).pl()
        if result.is_empty():
            return
        occurrences = int(result["occurrences"][0])
        classified = int(result["classified"][0])
        if occurrences != classified:
            logger.warning(
                f"Taxonomy status table has {classified} rows for {occurrences} "
                "occurrences; the variant join is not one-to-one."
            )

    def count_by_status(self) -> dict[str, int]:
        """Return the occurrence count per update status."""
        try:
            result = self.db_client.execute(
                f"""
                SELECT coalesce(update_status, 'UNCLASSIFIED') AS status,
                       count(*) AS total
                FROM {self.status_table}
                GROUP BY status ORDER BY total DESC
                """
            ).pl()
        except duckdb.Error as error:
            logger.error(f"Failed to summarize taxonomy update: {error}")
            return {}
        if result.is_empty():
            return {}
        return dict(zip(result["status"].to_list(), result["total"].to_list()))


def _ident(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


# Read back per occurrence. Codes only: their descriptions are served once by
# GET /taxonomy/codes rather than repeated on every record.
_STATUS_FIELDS = (
    ("update_status", "updateStatus"),
    ("match_method", "matchMethod"),
    ("accepted_name", "acceptedName"),
    ("accepted_species_name", "acceptedSpeciesName"),
    ("display_accepted_name", "displayAcceptedName"),
    ("accepted_rank", "acceptedRank"),
    ("accepted_authorship", "acceptedAuthorship"),
    ("accepted_family", "acceptedFamily"),
    ("accepted_status", "acceptedStatus"),
    ("match_score", "matchScore"),
    ("score_margin", "scoreMargin"),
    ("candidate_count", "candidateCount"),
    ("genus_changed", "genusChanged"),
    ("epithet_changed", "epithetChanged"),
    ("reason_code", "reasonCode"),
)

_CANDIDATE_FIELDS = (
    ("candidate_rank", "candidateRank"),
    ("accepted_name", "acceptedName"),
    ("accepted_authorship", "acceptedAuthorship"),
    ("accepted_rank", "acceptedRank"),
    ("accepted_family", "acceptedFamily"),
    ("candidate_method", "candidateMethod"),
    ("match_score", "matchScore"),
    ("genus_distance", "genusDistance"),
    ("epithet_distance", "epithetDistance"),
)


class OccurrenceTaxonomy:
    """Read the taxonomic update for a single occurrence image."""

    # Class-level default so the field is always readable, including on
    # instances built without __init__. Only ever rebound, never mutated.
    _status_present: bool | None = None

    def __init__(self, duckdb_client: DuckDBClient):
        config = ColConfig()
        self.status_table = config.occurrence_status_table
        self.candidates_table = config.candidates_table
        self.image_meta_table = ImageMetaConfig().table
        self.db_client = duckdb_client
        # Resolved on first use and cached for this instance, which lives for
        # one request.
        self._status_present = None

    def _status_available(self) -> bool:
        """Whether a colharmonize run has been loaded.

        Checked rather than discovered by failure: the metadata panel is
        fetched per image and prefetches its neighbours, so querying a table
        that is not there logs on every thumbnail. Startup already reports the
        absence once, through report_taxonomy_readiness.
        """
        if self._status_present is None:
            self._status_present = self.db_client.table_exists(self.status_table)
        return self._status_present

    def get_for_image(self, img_id: str) -> dict | None:
        """Return the update for an image, or None when there is none.

        None rather than a placeholder: the panel omits the whole block when no
        run has been loaded, instead of showing empty rows.
        """
        if not img_id or not self._status_available():
            return None
        try:
            result = self.db_client.execute_prepared_to_pl(
                f"""
                SELECT status.*, occurrence.species AS input_name
                FROM {self.status_table} AS status
                JOIN {self.image_meta_table} AS occurrence USING (img_id)
                WHERE status.img_id = ?
                LIMIT 1
                """,
                [img_id],
            )
        except duckdb.Error as error:
            # Expected before the first run is loaded: the table is absent.
            logger.info(f"No taxonomy status available for image '{img_id}': {error}")
            return None
        if result is None or result.is_empty():
            return None

        row = result.to_dicts()[0]
        if not row.get("update_status"):
            return None

        payload = {name: row.get(column) for column, name in _STATUS_FIELDS}
        payload["inputName"] = row.get("input_name")
        payload["candidates"] = self._candidates(row.get("input_taxon_key"))
        return payload

    def _candidates(self, input_taxon_key: str | None) -> list[dict]:
        """Return the runner-up candidates for a taxon, best first.

        Rank 1 is the selected match and is already shown as the accepted name,
        so only the alternatives are listed.
        """
        if not input_taxon_key:
            return []
        projection = ", ".join(column for column, _ in _CANDIDATE_FIELDS)
        try:
            result = self.db_client.execute_prepared_to_pl(
                f"""
                SELECT {projection}
                FROM {self.candidates_table}
                WHERE input_taxon_key = ? AND candidate_rank > 1
                ORDER BY candidate_rank
                """,
                [input_taxon_key],
            )
        except duckdb.Error as error:
            logger.info(f"No candidates available for '{input_taxon_key}': {error}")
            return []
        if result is None or result.is_empty():
            return []
        return [
            {name: row.get(column) for column, name in _CANDIDATE_FIELDS}
            for row in result.to_dicts()
        ]
