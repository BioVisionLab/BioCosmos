"""Catalogue of Life taxonomy backbone.

It uses taxonomy from ``NameUsage.tsv``.

Two facts drive the ingest:

* Lineage columns are populated only on accepted rows. Synonyms carry an empty
  lineage and a ``parentID`` pointing at their accepted taxon, so restricting to
  a clade has to be a seed-plus-children pass or synonym resolution breaks.
* The release covers all of life. ``clade_rank``/``clade_value`` narrow it to
  the group this collection actually holds.
"""

import logging
import re

import duckdb

from ..configs.config import ColConfig
from ..database.duckdb import DuckDBClient
from ..database.ingestion_state import IngestionState, file_fingerprint
from ..database.model import ColTaxonomy

logger = logging.getLogger(__name__)

# Logical name -> ColDP column. Values are quoted as identifiers when used.
COL_SOURCE_COLUMNS: dict[str, str] = {
    "usage_id": "col:ID",
    "parent_id": "col:parentID",
    "status": "col:status",
    "scientific_name": "col:scientificName",
    "authorship": "col:authorship",
    "taxon_rank": "col:rank",
    "generic_name": "col:genericName",
    "specific_epithet": "col:specificEpithet",
    "infraspecific_epithet": "col:infraspecificEpithet",
    "kingdom": "col:kingdom",
    "phylum": "col:phylum",
    "subphylum": "col:subphylum",
    "class": "col:class",
    "subclass": "col:subclass",
    "order": "col:order",
    "suborder": "col:suborder",
    "superfamily": "col:superfamily",
    "family": "col:family",
    "subfamily": "col:subfamily",
    "tribe": "col:tribe",
    "subtribe": "col:subtribe",
    "genus": "col:genus",
    "subgenus": "col:subgenus",
    "extinct": "col:extinct",
    "environment": "col:environment",
    "col_link": "col:link",
}

# Ranks worth keeping. Everything else in a release is unplaced or
# infrasubspecific detail the classification panel has no use for.
COL_KEPT_RANKS = (
    "species",
    "subspecies",
    "genus",
    "subgenus",
    "tribe",
    "subtribe",
    "subfamily",
    "family",
    "superfamily",
    "suborder",
    "order",
)

ACCEPTED_STATUSES = ("accepted", "provisionally accepted")

# CoL is read once per release; these are the lookups the API actually makes.
COL_INDEXES = {
    "col_taxonomy_name_idx": "(name_norm)",
    "col_taxonomy_usage_idx": "(usage_id)",
    "col_taxonomy_accepted_idx": "(accepted_id)",
    "col_taxonomy_canonical_idx": "(canonical_key)",
    "col_taxonomy_genus_idx": "(genus_norm)",
    "col_taxonomy_family_idx": "(family_norm)",
}

BACKBONE_SOURCE_KEY = "col_taxonomy"

# Logged once per process, not once per lookup: a single page view makes three
# lookups, and a whole search page many more.
_BACKBONE_WARNING_EMITTED = False


def _warn_backbone_missing(table: str) -> None:
    """Explain a missing backbone once, with the command that builds it."""
    global _BACKBONE_WARNING_EMITTED
    if _BACKBONE_WARNING_EMITTED:
        return
    _BACKBONE_WARNING_EMITTED = True
    logger.warning(
        f"Catalogue of Life backbone '{table}' is not in the database, so no "
        "classification can be served. Set COL_DIR to an extracted ColDP "
        "release and set col.skip to false in backend/app/configs/config.yaml, "
        "then restart to build it."
    )


def _quoted(name: str) -> str:
    """Quote a CoL column name, which contains a colon."""
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def _read_csv_expr(placeholder: str = "?") -> str:
    """A DuckDB read_csv call for a ColDP TSV.

    ``quote=''`` matters: ColDP fields carry bare double quotes inside remarks
    and authorship, which the default quoting rules would swallow.
    """
    return (
        f"read_csv({placeholder}, delim='\t', header=true, all_varchar=true, "
        "quote='', sample_size=-1, null_padding=true)"
    )


class ColBackboneService:
    """Ingest the CoL name usage table and its vernacular names."""

    def __init__(self, duckdb: DuckDBClient):
        config = ColConfig()
        self.config = config
        self.path = config.path
        self.vernacular_path = config.vernacular_path
        self.table = config.table
        self.vernacular_table = config.vernacular_table
        self.clade_rank = config.clade_rank
        self.clade_value = config.clade_value
        self.skip_ingestion = config.skip
        self.db_client = duckdb

    def ingest(self) -> None:
        """Load the backbone, skipping when the source has not changed."""
        if self.skip_ingestion:
            logger.info("Skipping CoL ingestion as per configuration.")
            return

        state = IngestionState(self.db_client)
        fingerprint = file_fingerprint(self.path)
        if fingerprint is None:
            logger.warning(
                f"CoL name usage file not found at '{self.path}'; skipping ingestion."
            )
            return
        if state.is_current(
            BACKBONE_SOURCE_KEY, fingerprint
        ) and self.db_client.table_exists(self.table):
            logger.info("CoL backbone is already current; skipping ingestion.")
            return

        try:
            self._ingest_name_usage()
            self._create_indexes()
            self._ingest_vernacular_names()
            state.mark(BACKBONE_SOURCE_KEY, fingerprint)
            logger.info(
                f"CoL backbone ingested: {self.count_entries()} usages "
                f"in '{self.table}'."
            )
        except Exception as error:
            logger.error(f"Failed to ingest CoL data from '{self.path}': {error}")
            raise

    def _ingest_name_usage(self) -> None:
        projection = ",\n            ".join(
            f"{_quoted(source)} AS {_quoted(logical)}"
            for logical, source in COL_SOURCE_COLUMNS.items()
        )
        ranks = ", ".join(f"'{rank}'" for rank in COL_KEPT_RANKS)
        accepted = ", ".join(f"'{status}'" for status in ACCEPTED_STATUSES)

        params: list[str] = [self.path]
        if self.clade_value and self.clade_rank:
            # The clade column is an identifier, so it cannot be bound; it comes
            # from config and is checked against the known column set.
            if self.clade_rank not in COL_SOURCE_COLUMNS:
                raise ValueError(
                    f"Unknown CoL clade_rank '{self.clade_rank}'. "
                    f"Expected one of: {', '.join(sorted(COL_SOURCE_COLUMNS))}"
                )
            seed_filter = f"WHERE {_quoted(self.clade_rank)} = ?"
            params.append(self.clade_value)
            logger.info(
                f"Restricting CoL backbone to {self.clade_rank} = {self.clade_value!r}."
            )
        else:
            seed_filter = ""
            logger.info("Ingesting the full CoL backbone (no clade filter).")

        query = f"""
            CREATE OR REPLACE TABLE {self.table} AS
            WITH src AS (
                SELECT
            {projection}
                FROM {_read_csv_expr()}
            ), seed AS (
                SELECT * FROM src {seed_filter}
            ), kept AS (
                SELECT * FROM seed
                UNION ALL
                -- Synonyms carry no lineage of their own; keep the ones whose
                -- accepted parent is inside the clade so they stay resolvable.
                SELECT child.* FROM src AS child
                JOIN seed ON child.parent_id = seed.usage_id
                WHERE child.usage_id NOT IN (SELECT usage_id FROM seed)
            ), normalized AS (
                SELECT
                    * EXCLUDE (taxon_rank),
                    lower(taxon_rank) AS taxon_rank,
                    -- Mirrors ImageMetaService.sanitize_species_name so
                    -- occurrence names such as 'coenonympha_pamphilus' join.
                    lower(regexp_replace(trim(replace(scientific_name, '_', ' ')),
                                         '\\s+', ' ', 'g')) AS name_norm,
                    -- CoL writes zoological names with the subgenus in
                    -- parentheses ('Danaus (Danaus) plexippus'), which no
                    -- occurrence record carries. Dropping it is what makes
                    -- those names findable.
                    lower(trim(regexp_replace(
                        regexp_replace(trim(replace(scientific_name, '_', ' ')),
                                       '\\s*\\([^)]+\\)\\s*', ' ', 'g'),
                        '\\s+', ' ', 'g'))) AS parsed_name,
                    lower(nullif(trim(family), '')) AS family_norm,
                    lower(status) IN ({accepted}) AS is_accepted,
                    CASE WHEN lower(status) IN ({accepted})
                         THEN usage_id ELSE parent_id END AS accepted_id
                FROM kept
                WHERE lower(taxon_rank) IN ({ranks})
            ), keyed AS (
                SELECT *,
                    lower(coalesce(
                        nullif(trim(generic_name), ''),
                        regexp_extract(parsed_name, '^([^ ]+)', 1))) AS genus_norm,
                    lower(coalesce(
                        nullif(trim(specific_epithet), ''),
                        regexp_extract(parsed_name, '^[^ ]+ ([^ ]+)', 1))) AS epithet_norm,
                    lower(nullif(trim(infraspecific_epithet), ''))
                        AS infraspecific_norm
                FROM normalized
            )
            SELECT * EXCLUDE (parsed_name),
                -- Genus plus epithet, free of subgenus notation: the form an
                -- occurrence name is actually written in.
                CASE taxon_rank
                    WHEN 'genus' THEN genus_norm
                    WHEN 'subspecies' THEN
                        nullif(concat_ws(' ', genus_norm, epithet_norm,
                                         infraspecific_norm), '')
                    ELSE nullif(concat_ws(' ', genus_norm, epithet_norm), '')
                END AS canonical_key
            FROM keyed
        """
        self.db_client.execute_prepared(query, params)

    def _create_indexes(self) -> None:
        for index_name, columns in COL_INDEXES.items():
            self.db_client.execute(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON {self.table} {columns}"
            )

    def _ingest_vernacular_names(self) -> None:
        """Load common names for the ingested usages.

        CoL replaces GBIF's ``vernacularName``. English preferred names win;
        ``image_meta.common_name`` remains the per-occurrence fallback.
        """
        if file_fingerprint(self.vernacular_path) is None:
            logger.info(
                f"No CoL vernacular file at '{self.vernacular_path}'; "
                "common names will fall back to occurrence metadata."
            )
            self.db_client.execute(
                f"""
                CREATE OR REPLACE TABLE {self.vernacular_table} (
                    usage_id VARCHAR, vernacular_name VARCHAR, language VARCHAR
                )
                """
            )
            return

        self.db_client.execute_prepared(
            f"""
            CREATE OR REPLACE TABLE {self.vernacular_table} AS
            WITH src AS (
                SELECT
                    "col:taxonID" AS usage_id,
                    "col:name" AS vernacular_name,
                    lower("col:language") AS language,
                    lower("col:preferred") AS preferred
                FROM {_read_csv_expr()}
            ), scoped AS (
                SELECT * FROM src
                WHERE usage_id IN (SELECT usage_id FROM {self.table})
                  AND nullif(trim(vernacular_name), '') IS NOT NULL
            ), ranked AS (
                SELECT *, row_number() OVER (
                    PARTITION BY usage_id
                    ORDER BY (language = 'eng') DESC,
                             (preferred IN ('true', '1')) DESC,
                             vernacular_name
                ) AS name_rank
                FROM scoped
            )
            SELECT usage_id, vernacular_name, language
            FROM ranked WHERE name_rank = 1
            """,
            [self.vernacular_path],
        )
        self.db_client.execute(
            f"CREATE INDEX IF NOT EXISTS col_vernacular_usage_idx "
            f"ON {self.vernacular_table} (usage_id)"
        )

    def count_entries(self) -> int | None:
        """Count the usages in the ingested backbone."""
        try:
            result = self.db_client.execute(
                f"SELECT COUNT(*) AS total FROM {self.table}"
            ).pl()
            return result["total"][0] if not result.is_empty() else None
        except duckdb.Error as error:
            logger.error(f"Failed to count CoL backbone entries: {error}")
            return None


# Columns read back for a classification. Ordered for readability only.
COL_LOOKUP_COLUMNS = (
    "usage_id",
    "scientific_name",
    "authorship",
    "status",
    "taxon_rank",
    "kingdom",
    "phylum",
    "subphylum",
    "class",
    "subclass",
    "order",
    "suborder",
    "superfamily",
    "family",
    "subfamily",
    "tribe",
    "subtribe",
    "genus",
    "subgenus",
    "extinct",
    "environment",
    "col_link",
)


def _normalize_name(name: str) -> str:
    """Normalize a queried name the way the backbone's name_norm is built."""
    return " ".join(name.strip().replace("_", " ").split()).lower()


def _canonical_name(name: str) -> str:
    """Drop any parenthesised subgenus, matching the backbone's canonical_key."""
    return " ".join(re.sub(r"\([^)]*\)", " ", name.replace("_", " ")).split()).lower()


class ColTaxonSearch:
    """Resolve names against the local CoL backbone.

    Replaces GbifTaxonSearch, which issued a live `?name=...&limit=1` request to
    the GBIF API per species page and took the first result without checking its
    status. This reads the ingested backbone instead: no network call, and a
    synonym resolves to the taxon CoL actually accepts.
    """

    # Class-level default so the field is always readable, including on
    # instances built without __init__. Only ever rebound, never mutated.
    _backbone_present: bool | None = None

    def __init__(self, duckdb: DuckDBClient):
        config = ColConfig()
        self.table = config.table
        self.vernacular_table = config.vernacular_table
        self.matches_table = config.matches_table
        self.db_client = duckdb
        # Resolved on first use and cached for this instance, which lives for
        # one request.
        self._backbone_present = None

    def _backbone_available(self) -> bool:
        """Whether the backbone has been ingested.

        Without this, every lookup runs a query against a table that is not
        there and logs a catalog error, three times per species page.
        """
        if self._backbone_present is None:
            self._backbone_present = self.db_client.table_exists(self.table)
            if not self._backbone_present:
                _warn_backbone_missing(self.table)
        return self._backbone_present

    def _resolution_query(self, predicate: str) -> str:
        """Build the accepted-usage lookup for a `hit` predicate.

        The hit is joined to the usage its `accepted_id` names, so a synonym
        yields the accepted taxon. The join is a LEFT JOIN with a COALESCE
        fallback: a synonym whose accepted parent fell outside the ingested
        clade still resolves to itself rather than vanishing.
        """
        projection = ",\n                ".join(
            f"coalesce(accepted.{_quoted(column)}, hit.{_quoted(column)}) "
            f"AS {_quoted(column)}"
            for column in COL_LOOKUP_COLUMNS
        )
        return f"""
            WITH hit AS (
                SELECT * FROM {self.table}
                WHERE {predicate}
                -- Prefer an accepted usage when a name is used by several.
                ORDER BY is_accepted DESC, usage_id
                LIMIT 1
            )
            SELECT
                {projection},
                hit.scientific_name AS hit_name,
                hit.status AS hit_status,
                vernacular.vernacular_name AS vernacular_name
            FROM hit
            LEFT JOIN {self.table} AS accepted
                   ON accepted.usage_id = hit.accepted_id
            LEFT JOIN {self.vernacular_table} AS vernacular
                   ON vernacular.usage_id = coalesce(accepted.usage_id, hit.usage_id)
        """

    def _lookup(
        self,
        predicate: str,
        params: list,
        query: str,
        *,
        input_name: str | None = None,
    ) -> dict | None:
        if not self._backbone_available():
            return None
        try:
            result = self.db_client.execute_prepared_to_pl(
                self._resolution_query(predicate), params
            )
        except duckdb.Error as error:
            logger.error(f"CoL lookup failed for '{query}': {error}")
            return None
        if result is None or result.is_empty():
            logger.info(f"No CoL data found for: {query}")
            return None

        row = result.to_dicts()[0]
        # Keep the name that was asked for when it differs from the accepted one.
        if input_name is None:
            hit_name = row.get("hit_name")
            if hit_name != row.get("scientific_name"):
                input_name = hit_name
        taxon = ColTaxonomy.from_row(row, input_name=input_name)
        return taxon.model_dump(by_alias=True)

    async def search(self, query: str) -> dict | None:
        """Resolve a scientific name to its accepted CoL classification.

        Tries the name as written, then its canonical genus-plus-epithet form.
        The second pass is what finds the many zoological names CoL records
        with a subgenus — 'Danaus (Danaus) plexippus' for a collection that
        only ever writes 'danaus_plexippus'.

        Async to match the call sites this replaces; the work is a local query.
        """
        normalized = _normalize_name(query or "")
        if not normalized:
            return None
        found = self._lookup("name_norm = ?", [normalized], query)
        if found:
            return found

        canonical = _canonical_name(query)
        if canonical and canonical != normalized:
            found = self._lookup("canonical_key = ?", [canonical], query)
        else:
            # Nothing was stripped, so a canonical pass on the same string is
            # still worth trying against names that do carry a subgenus.
            found = self._lookup("canonical_key = ?", [normalized], query)
        if found:
            return found

        return self._resolve_through_update(normalized, query)

    def _resolve_through_update(self, normalized: str, query: str) -> dict | None:
        """Fall back to what the harmonization run resolved this name to.

        Roughly 8% of the collection's names have no CoL usage of their own —
        they were reassigned to another genus, or misspelled — so no exact
        lookup can find them. colharmonize already resolved those by family
        and epithet, and its `accepted_id` is a CoL usage id, so its answer
        can be looked up here directly.

        Absent before the first run is loaded, in which case nothing matches
        and the caller sees no classification, as before.
        """
        return self._lookup(
            f"""usage_id = (
                    SELECT accepted_id FROM {self.matches_table}
                    WHERE normalized_name = ? AND accepted_id IS NOT NULL
                    ORDER BY match_score DESC
                    LIMIT 1
                )""",
            [normalized],
            query,
            # Reaching here means CoL has no usage under the queried name, so
            # the accepted name is necessarily a different one. The lookup was
            # by id, so the row cannot report that on its own.
            input_name=query.replace("_", " ").strip(),
        )

    async def search_at_rank(self, query: str, rank: str) -> dict | None:
        """Resolve a name that must sit at a given rank, e.g. family or genus."""
        normalized = _normalize_name(query or "")
        if not normalized:
            return None
        rank_norm = rank.strip().lower()
        found = self._lookup(
            "name_norm = ? AND taxon_rank = ?",
            [normalized, rank_norm],
            f"{query} ({rank})",
        )
        if found:
            return found
        return self._lookup(
            "canonical_key = ? AND taxon_rank = ?",
            [_canonical_name(query) or normalized, rank_norm],
            f"{query} ({rank})",
        )

    async def close(self) -> None:
        """No-op kept for symmetry with the HTTP client this replaced."""
