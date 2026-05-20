import logging

import polars as pl
from fastapi import Request

from ..database.duckdb import DuckDBClient
from .species_similarity import VisuallySimilarSpeciesPayload

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

    def find_similar_species(self, species_name: str) -> dict | None:
        """
        Find precomputed similar species. Returns dict matching
        VisuallySimilarSpeciesPayload shape, or None if unavailable.
        """
        normalized = species_name.strip().lower().replace(" ", "_")

        try:
            if not self._table_exists():
                return None

            dorsal = self._query_side(normalized, "dorsal")
            ventral = self._query_side(normalized, "ventral")

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

    def _query_side(self, species: str, side: str) -> list[dict]:
        """Query precomputed results for a species and side."""
        query = f"""
            SELECT similar_species AS species,
                   img_id AS imgId,
                   distance
            FROM {SIMILARITY_TABLE}
            WHERE species = ? AND side = ?
            ORDER BY rank ASC
            LIMIT ?
        """
        result = self.duck_db.execute_prepared_to_pl(
            query, [species, side, self.limit]
        )

        if result is None or result.is_empty():
            return []

        return result.to_dicts()

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
