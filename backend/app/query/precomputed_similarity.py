import logging

import polars as pl
from fastapi import Request

from ..database.duckdb import DuckDBClient
from ..services.taxonomy_update import OccurrenceTaxonomy
from .species_similarity import (
    VisuallySimilarSpeciesPayload,
    resolve_similar_species,
)

logger = logging.getLogger(__name__)

SIMILARITY_TABLE = "species_similarity"


class PrecomputedSpeciesSimilarity:
    """
    Read precomputed species similarity results from DuckDB.
    Returns None when the table is missing or has no data for a species,
    allowing the caller to fall back to runtime vector search.
    """

    def __init__(self, request: Request, limit: int = 10):
        self.duck_db: DuckDBClient = request.app.state.duck_db
        self.limit = limit
        # One lookup for both sides; it caches its own table probe.
        self.taxonomy = OccurrenceTaxonomy(duckdb_client=self.duck_db)

    def find_similar_species(
        self, species_name: str, side: str | None = None
    ) -> dict | None:
        """
        Find precomputed similar species. Returns dict matching
        VisuallySimilarSpeciesPayload shape, or None if unavailable.

        With `side` given, only that side is queried and the other comes back
        empty. The panel asks for the two sides separately so whichever
        resolves first can paint, and querying only what was asked for is what
        makes that worth doing.

        Note what "unavailable" then means: with a side given, None is returned
        when *that* side has nothing, so the caller falls back to a runtime
        vector search for it. Unscoped, it takes both sides being empty. A
        species with dorsal rows but no ventral ones therefore now gets a
        runtime search for ventral where the combined call served an empty
        list -- which is the more correct answer, not an accident.
        """
        normalized = species_name.strip().lower().replace(" ", "_")

        try:
            if not self._table_exists():
                return None

            # The stored rows are keyed on the name each record was filed
            # under, so they are resolved here rather than at build time. That
            # keeps the precomputed table a pure nearest-neighbour index, and
            # means a new harmonization run changes what the panel says
            # without the offline script having to be run again.
            exclude_keys = self.taxonomy.accepted_keys_for_species(normalized)
            dorsal = (
                self._query_side(normalized, "dorsal", exclude_keys)
                if side in (None, "dorsal")
                else []
            )
            ventral = (
                self._query_side(normalized, "ventral", exclude_keys)
                if side in (None, "ventral")
                else []
            )

            if not dorsal and not ventral:
                return None

            payload = VisuallySimilarSpeciesPayload(
                dorsal=dorsal,
                ventral=ventral,
            )
            return payload.model_dump(by_alias=True)

        except Exception as e:
            logger.error(
                f"Error reading precomputed similarity for {species_name}: {e}",
                exc_info=True,
            )
            return None

    def _query_side(
        self, species: str, side: str, exclude_keys: set[str]
    ) -> list[dict]:
        """Query precomputed results for a species and side.

        Every stored row is read, not the first `limit`: resolving collapses
        the spellings of one taxon into a single card, so cutting first would
        leave the panel shorter than it needs to be.
        """
        query = f"""
            SELECT similar_species AS species,
                   img_id AS imgId,
                   distance
            FROM {SIMILARITY_TABLE}
            WHERE species = ? AND side = ?
            ORDER BY rank ASC
        """
        result = self.duck_db.execute_prepared_to_pl(query, [species, side])

        if result is None or result.is_empty():
            return []

        return resolve_similar_species(
            result.to_dicts(), self.taxonomy, exclude_keys, self.limit
        )

    def _table_exists(self) -> bool:
        """Check if the precomputed similarity table exists."""
        try:
            result = self.duck_db.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                f"WHERE table_name = '{SIMILARITY_TABLE}'"
            ).fetchone()
            return result[0] > 0
        except Exception:
            return False
