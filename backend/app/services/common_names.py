"""Resolve stored common names to the recorded species used by image search."""

import re

from ..configs.config import ColConfig, ImageMetaConfig
from ..database.duckdb import DuckDBClient


def _identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


class CommonNameSearch:
    def __init__(self, duckdb: DuckDBClient):
        self.db_client = duckdb
        self.image_table = ImageMetaConfig().table
        config = ColConfig()
        self.backbone_table = config.table
        self.vernacular_table = config.vernacular_table
        self.taxonomy_table = config.occurrence_status_table

    def search(self, name: str) -> list[str]:
        """Prefer exact names, then literal whole-word phrases, across both stores."""
        normalized = " ".join(name.lower().split())
        if not normalized:
            return []
        images = _identifier(self.image_table)
        sources = [f"SELECT species, common_name AS name FROM {images}"]
        if self.db_client.table_exists(self.vernacular_table):
            vernacular = _identifier(self.vernacular_table)
            if self.db_client.table_exists(self.backbone_table):
                backbone = _identifier(self.backbone_table)
                sources.append(f"""
                    SELECT images.species, names.vernacular_name AS name
                    FROM {images} AS images
                    JOIN {backbone} AS taxa ON taxa.canonical_key =
                        lower(regexp_replace(trim(replace(images.species, '_', ' ')),
                                             '\\s+', ' ', 'g'))
                    JOIN {vernacular} AS names
                      ON names.usage_id IN (taxa.usage_id, taxa.accepted_id)
                """)
            if self.db_client.table_exists(self.taxonomy_table):
                taxonomy = _identifier(self.taxonomy_table)
                sources.append(f"""
                    SELECT images.species, names.vernacular_name AS name
                    FROM {images} AS images
                    JOIN {taxonomy} AS taxonomy USING (img_id)
                    JOIN {vernacular} AS names
                      ON names.usage_id = taxonomy.accepted_id
                """)
        # The exact-match preference is global across sources and only considers
        # names associated with actual image records. Regex syntax is escaped.
        pattern = r"(^|[^\p{L}\p{N}_])" + re.escape(normalized) + r"($|[^\p{L}\p{N}_])"
        result = self.db_client.execute_prepared_to_pl(
            f"""
            WITH names AS ({" UNION ALL ".join(sources)}), normalized AS (
                SELECT species,
                    lower(regexp_replace(trim(name), '\\s+', ' ', 'g')) AS name
                FROM names
                WHERE nullif(trim(species), '') IS NOT NULL
                  AND nullif(trim(name), '') IS NOT NULL
            ), matches AS (
                SELECT species, name = ? AS exact FROM normalized
                WHERE name = ? OR regexp_matches(name, ?)
            )
            SELECT DISTINCT species FROM matches
            WHERE exact OR NOT EXISTS (SELECT 1 FROM matches WHERE exact)
            ORDER BY species
            """,
            [normalized, normalized, pattern],
        )
        return result["species"].to_list()
