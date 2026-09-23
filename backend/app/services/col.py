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
from ..database.model import (
    ColNameUsage,
    ColNomenclature,
    ColReference,
    ColTaxonomy,
    ColTaxonomyDetail,
    ColTypeSpecimen,
    binomial_name,
    year_from,
)

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
    # Nomenclature, for the taxonomy tab: where a name was published and which
    # usage is its original combination.
    "basionym_id": "col:basionymID",
    "name_reference_id": "col:nameReferenceID",
    "name_published_in_page": "col:namePublishedInPage",
    "name_status": "col:nameStatus",
}

# TypeMaterial.tsv, logical name -> ColDP column. `nameID` is a NameUsage ID in
# a merged release, so it joins straight onto `col_taxonomy.usage_id`.
TYPE_MATERIAL_COLUMNS: dict[str, str] = {
    "name_id": "col:nameID",
    "status": "col:status",
    "citation": "col:citation",
    "reference_id": "col:referenceID",
    "page": "col:page",
    "country": "col:country",
    "locality": "col:locality",
    "latitude": "col:latitude",
    "longitude": "col:longitude",
    "altitude": "col:altitude",
    "sex": "col:sex",
    "host": "col:host",
    "collection_date": "col:date",
    "collector": "col:collector",
    "institution_code": "col:institutionCode",
    "catalog_number": "col:catalogNumber",
    "link": "col:link",
    "remarks": "col:remarks",
}

# Reference.tsv, logical name -> ColDP column.
REFERENCE_COLUMNS: dict[str, str] = {
    "reference_id": "col:ID",
    "citation": "col:citation",
    "author": "col:author",
    "title": "col:title",
    "container_title": "col:containerTitle",
    "issued": "col:issued",
    "volume": "col:volume",
    "page": "col:page",
    "doi": "col:doi",
    "link": "col:link",
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

# Congeners are only used to label genus-level literature hits, so a large
# genus does not need every member; this keeps the payload bounded.
MAX_CONGENERS = 200

# Type statuses in the order a reader looks for them: the name-bearing type
# first, then the rest of the type series. Anything unlisted sorts last.
TYPE_STATUS_ORDER = (
    "holotype",
    "neotype",
    "lectotype",
    "syntype",
    "allotype",
    "paratype",
    "paralectotype",
    "paraneotype",
)

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
        self.type_material_path = config.type_material_path
        self.type_material_table = config.type_material_table
        self.reference_path = config.reference_path
        self.reference_table = config.reference_table
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
        if (
            state.is_current(BACKBONE_SOURCE_KEY, fingerprint)
            and self._schema_current()
        ):
            logger.info("CoL backbone is already current; skipping ingestion.")
            return

        try:
            self._ingest_name_usage()
            self._create_indexes()
            self._ingest_vernacular_names()
            self._ingest_type_material()
            self._ingest_references()
            state.mark(BACKBONE_SOURCE_KEY, fingerprint)
            logger.info(
                f"CoL backbone ingested: {self.count_entries()} usages "
                f"in '{self.table}'."
            )
        except Exception as error:
            logger.error(f"Failed to ingest CoL data from '{self.path}': {error}")
            raise

    def _schema_current(self) -> bool:
        """Whether the database holds everything this code reads.

        The fingerprint only tracks NameUsage.tsv, so a database built before
        the nomenclature columns and the type-material and reference tables
        existed would otherwise never gain them.
        """
        return not self.db_client.missing_tables(
            [self.table, self.type_material_table, self.reference_table]
        ) and self.db_client.column_exists(self.table, "basionym_id")

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

    def _ingest_scoped(
        self,
        path: str,
        table: str,
        columns: dict[str, str],
        scope: str,
        label: str,
    ) -> None:
        """Load a ColDP table, keeping only the rows `scope` selects.

        A missing file yields an empty table with the same columns, so lookups
        degrade to "nothing recorded" rather than a catalog error.
        """
        if file_fingerprint(path) is None:
            logger.info(f"No CoL {label} file at '{path}'; '{table}' will be empty.")
            definition = ", ".join(f"{_quoted(name)} VARCHAR" for name in columns)
            self.db_client.execute(f"CREATE OR REPLACE TABLE {table} ({definition})")
            return

        projection = ",\n                ".join(
            f"nullif(trim({_quoted(source)}), '') AS {_quoted(logical)}"
            for logical, source in columns.items()
        )
        self.db_client.execute_prepared(
            f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT
                {projection}
            FROM {_read_csv_expr()}
            WHERE {scope}
            """,
            [path],
        )

    def _ingest_type_material(self) -> None:
        """Load the type specimens of the ingested names."""
        self._ingest_scoped(
            self.type_material_path,
            self.type_material_table,
            TYPE_MATERIAL_COLUMNS,
            f'"col:nameID" IN (SELECT usage_id FROM {self.table})',
            "type material",
        )
        self.db_client.execute(
            f"CREATE INDEX IF NOT EXISTS col_type_material_name_idx "
            f"ON {self.type_material_table} (name_id)"
        )

    def _ingest_references(self) -> None:
        """Load the references the ingested names and type specimens cite.

        Reference.tsv covers all of life and is several hundred megabytes, so
        only the cited rows are kept. Runs after the type material, whose
        citations are part of the scope.
        """
        self._ingest_scoped(
            self.reference_path,
            self.reference_table,
            REFERENCE_COLUMNS,
            f""""col:ID" IN (
                SELECT name_reference_id FROM {self.table}
                WHERE name_reference_id IS NOT NULL
                UNION
                SELECT reference_id FROM {self.type_material_table}
                WHERE reference_id IS NOT NULL
            )""",
            "reference",
        )
        self.db_client.execute(
            f"CREATE INDEX IF NOT EXISTS col_reference_id_idx "
            f"ON {self.reference_table} (reference_id)"
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
    # Defaults for instances built without __init__, as the tests do.
    type_material_table = "col_type_material"
    reference_table = "col_reference"

    def __init__(self, duckdb: DuckDBClient):
        config = ColConfig()
        self.table = config.table
        self.vernacular_table = config.vernacular_table
        self.matches_table = config.matches_table
        self.type_material_table = config.type_material_table
        self.reference_table = config.reference_table
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

    async def name_usages(self, query: str) -> dict | None:
        """Every name a species has been published under, plus its congeners.

        The literature search needs more than the accepted name: papers written
        before a genus transfer use the old combination, and a species with
        little literature of its own is best put in context by its genus. Both
        lists come from the ingested backbone, one query each.

        Returns None when the name does not resolve to a species.
        """
        taxon = await self.search(query)
        if not taxon or not taxon.get("species") or not taxon.get("colId"):
            return None
        accepted_id = taxon["colId"]
        accepted_name = taxon["species"]
        genus = taxon.get("genus") or accepted_name.split(" ")[0]

        synonyms: list[dict] = []
        seen = {accepted_name.lower()}
        try:
            rows = self.db_client.execute_prepared_to_pl(
                f"""
                SELECT scientific_name, authorship, status
                FROM {self.table}
                WHERE accepted_id = ? AND NOT is_accepted
                  AND taxon_rank = 'species'
                ORDER BY scientific_name
                """,
                [accepted_id],
            )
            for row in [] if rows is None else rows.to_dicts():
                name = binomial_name(row["scientific_name"] or "")
                if name.count(" ") != 1 or name.lower() in seen:
                    continue
                seen.add(name.lower())
                synonyms.append(
                    {
                        "name": name,
                        "authorship": (row.get("authorship") or "").strip() or None,
                        "status": (row.get("status") or "synonym").strip(),
                    }
                )

            # The name the collection recorded counts too: it is what the page
            # was reached by. Added after CoL's synonyms so a name CoL also
            # lists keeps its authorship.
            input_name = taxon.get("inputName")
            if input_name:
                recorded = binomial_name(input_name.replace("_", " ")).capitalize()
                if recorded.count(" ") == 1 and recorded.lower() not in seen:
                    seen.add(recorded.lower())
                    synonyms.append(
                        {"name": recorded, "authorship": None, "status": "recorded"}
                    )
                recorded_key = recorded.lower()
            else:
                recorded_key = None

            # Most useful first, since a caller may only search a few: the name
            # the collection recorded, then recombinations of the accepted
            # epithet (the original combination and earlier genus placements,
            # which is how older papers name the species), then the rest.
            epithet = accepted_name.split(" ")[-1].lower()
            synonyms.sort(
                key=lambda s: (
                    s["name"].lower() != recorded_key,
                    s["name"].split(" ")[-1].lower() != epithet,
                )
            )

            rows = self.db_client.execute_prepared_to_pl(
                f"""
                SELECT DISTINCT scientific_name
                FROM {self.table}
                WHERE genus_norm = ? AND is_accepted
                  AND taxon_rank = 'species' AND usage_id <> ?
                ORDER BY scientific_name
                LIMIT {MAX_CONGENERS}
                """,
                [genus.lower(), accepted_id],
            )
            congeners = sorted(
                {
                    name
                    for row in ([] if rows is None else rows.to_dicts())
                    if (name := binomial_name(row["scientific_name"] or ""))
                    and name.lower() != accepted_name.lower()
                }
            )
        except duckdb.Error as error:
            logger.error(f"CoL name usage lookup failed for '{query}': {error}")
            congeners = []

        return {
            "accepted_name": accepted_name,
            "genus": genus,
            "family": taxon.get("family") or None,
            "synonyms": synonyms,
            "congeners": congeners,
        }

    def _detail_available(self) -> bool:
        """Whether the nomenclature columns and their tables were ingested."""
        return not self.db_client.missing_tables(
            [self.type_material_table, self.reference_table]
        ) and self.db_client.column_exists(self.table, "basionym_id")

    def _reference_columns(self, alias: str, prefix: str) -> str:
        return ", ".join(
            f"{alias}.{_quoted(column)} AS {_quoted(prefix + column)}"
            for column in REFERENCE_COLUMNS
            if column != "reference_id"
        )

    async def taxonomy_detail(self, query: str) -> dict | None:
        """Classification, nomenclature, name usages and type material.

        Types are attached to the name they were designated for, which for a
        recombined species is its original combination rather than the
        accepted name, so they are gathered across every usage of the taxon.

        Returns None when the name does not resolve to a species.
        """
        taxon = await self.search(query)
        if not taxon or not taxon.get("species") or not taxon.get("colId"):
            return None
        accepted_id = taxon["colId"]
        detail = self._detail_available()

        try:
            usages = self._usage_rows(accepted_id, detail)
            usage_ids = [row["usage_id"] for row in usages]
            types = self._type_rows(usage_ids) if detail and usage_ids else []
        except duckdb.Error as error:
            logger.error(f"CoL taxonomy detail lookup failed for '{query}': {error}")
            usages, types = [], []

        name_usages = [self._name_usage(row, accepted_id) for row in usages]
        # Accepted name, then the original combination, then the rest by date.
        name_usages.sort(
            key=lambda usage: (
                not usage.isAccepted,
                not usage.isBasionym,
                usage.year or 9999,
                usage.name.lower(),
            )
        )
        input_name = taxon.get("inputName")
        if input_name:
            recorded = binomial_name(input_name.replace("_", " ")).capitalize()
            known = {binomial_name(usage.name).lower() for usage in name_usages}
            if recorded and recorded.lower() not in known:
                name_usages.append(
                    ColNameUsage(name=recorded, status="recorded", isRecorded=True)
                )

        detail_payload = ColTaxonomyDetail(
            classification=ColTaxonomy.model_validate(taxon),
            nomenclature=self._nomenclature(taxon, usages, accepted_id),
            nameUsages=name_usages,
            typeMaterial=[
                ColTypeSpecimen.from_row(row)
                for row in sorted(types, key=self._type_sort_key)
            ],
            detailAvailable=detail,
        )
        return detail_payload.model_dump(by_alias=True)

    def _usage_rows(self, accepted_id: str, detail: bool) -> list[dict]:
        """The accepted usage, its synonyms, and its basionym if elsewhere."""
        if detail:
            extra = f"""
                u.name_status, u.name_published_in_page,
                coalesce(u.usage_id = acc.basionym_id, false) AS is_basionym,
                {self._reference_columns("r", "ref_")}
            """
            basionym_clause = "OR u.usage_id = acc.basionym_id"
            reference_join = (
                f"LEFT JOIN {self.reference_table} AS r "
                "ON r.reference_id = u.name_reference_id"
            )
        else:
            extra = """
                NULL AS name_status, NULL AS name_published_in_page,
                false AS is_basionym
            """
            basionym_clause = ""
            reference_join = ""
        rows = self.db_client.execute_prepared_to_pl(
            f"""
            SELECT u.usage_id, u.scientific_name, u.authorship, u.status,
                   u.taxon_rank, {extra}
            FROM {self.table} AS u
            JOIN {self.table} AS acc ON acc.usage_id = ?
            {reference_join}
            WHERE (u.usage_id = acc.usage_id
                   OR (u.accepted_id = acc.usage_id AND NOT u.is_accepted)
                   {basionym_clause})
              AND u.taxon_rank IN ('species', 'subspecies')
            """,
            [accepted_id],
        )
        return [] if rows is None else rows.to_dicts()

    def _type_rows(self, usage_ids: list[str]) -> list[dict]:
        placeholders = ", ".join("?" for _ in usage_ids)
        rows = self.db_client.execute_prepared_to_pl(
            f"""
            SELECT t.*, u.scientific_name AS typified_name,
                   {self._reference_columns("r", "ref_")}
            FROM {self.type_material_table} AS t
            JOIN {self.table} AS u ON u.usage_id = t.name_id
            LEFT JOIN {self.reference_table} AS r
                   ON r.reference_id = t.reference_id
            WHERE t.name_id IN ({placeholders})
            """,
            usage_ids,
        )
        return [] if rows is None else rows.to_dicts()

    @staticmethod
    def _type_sort_key(row: dict) -> tuple:
        status = (row.get("status") or "").strip().lower()
        order = (
            TYPE_STATUS_ORDER.index(status)
            if status in TYPE_STATUS_ORDER
            else len(TYPE_STATUS_ORDER)
        )
        return (
            order,
            row.get("typified_name") or "",
            row.get("catalog_number") or "",
        )

    @staticmethod
    def _name_usage(row: dict, accepted_id: str) -> ColNameUsage:
        authorship = (row.get("authorship") or "").strip() or None
        reference = ColReference.from_row(row, "ref_")
        return ColNameUsage(
            colId=row.get("usage_id"),
            name=(row.get("scientific_name") or "").strip(),
            authorship=authorship,
            rank=row.get("taxon_rank"),
            status=(row.get("status") or "synonym").strip(),
            isAccepted=row.get("usage_id") == accepted_id,
            isBasionym=bool(row.get("is_basionym"))
            and row.get("usage_id") != accepted_id,
            nameStatus=(row.get("name_status") or "").strip() or None,
            publishedIn=reference,
            publishedInPage=(row.get("name_published_in_page") or "").strip() or None,
            year=year_from(authorship) or (reference.year if reference else None),
        )

    @staticmethod
    def _nomenclature(
        taxon: dict, usages: list[dict], accepted_id: str
    ) -> ColNomenclature:
        accepted = next((row for row in usages if row["usage_id"] == accepted_id), {})
        basionym = next(
            (
                row
                for row in usages
                if row.get("is_basionym") and row["usage_id"] != accepted_id
            ),
            None,
        )
        authorship = (
            accepted.get("authorship") or taxon.get("authorship") or ""
        ).strip() or None
        source = basionym or accepted
        reference = ColReference.from_row(source, "ref_") if source else None

        if basionym:
            is_original = False
        elif authorship and authorship.startswith("("):
            # Parenthesized authorship means the species was described in
            # another genus, but CoL does not link which combination.
            is_original = None
        else:
            is_original = True

        original_authorship = (
            (basionym.get("authorship") or "").strip() or None if basionym else None
        )
        return ColNomenclature(
            acceptedName=accepted.get("scientific_name")
            or taxon.get("scientificName")
            or taxon.get("species"),
            authorship=authorship,
            nameStatus=(accepted.get("name_status") or "").strip() or None,
            originalCombination=basionym.get("scientific_name") if basionym else None,
            originalAuthorship=original_authorship,
            isOriginalCombination=is_original,
            originalPublication=reference,
            originalPublicationPage=(
                (source.get("name_published_in_page") or "").strip() or None
                if source
                else None
            ),
            year=year_from(original_authorship or authorship)
            or (reference.year if reference else None),
        )

    async def close(self) -> None:
        """No-op kept for symmetry with the HTTP client this replaced."""
