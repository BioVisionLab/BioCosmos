import logging
import polars as pl

from ..configs.config import ImageMetaConfig, UmapDataConfig
from ..database.duckdb import DuckDBClient
from ..database.model import UmapEmbedding, UmapData

logger = logging.getLogger(__name__)

class SpeciesImageUmap:
    """
    Service class for UMAP data processing.
    """

    def __init__(self, duckdb: DuckDBClient):
        config = UmapDataConfig()
        self.path = config.path
        self.table = config.table
        self.skip_ingestion = config.skip
        self.db_client = duckdb

    def ingest(self):
        """
        Ingest UMAP data into the database.
        """
        if self.skip_ingestion:
            logger.info(
                "Skipping UMAP data ingestion as per configuration."
            )
            return
        try:
            self.db_client.create_or_replace_table_csv(
                table_name=self.table, csv_path=self.path
            )
            entries: int | None = self.count_entries()
            if entries is not None:
                logger.info(
                    f"UMAP data ingested successfully from '{self.path}'."
                )
                logger.info(
                    f"Total entries after ingestion: {entries}"
                )
        except Exception as e:
            logger.error(
                f"Failed to ingest UMAP data into '{self.table}': {e}"
            )
            raise e

    def count_entries(self) -> int | None:
        """
        Count the number of entries in the UMAP table.
        """
        try:
            query = f"SELECT COUNT(*) AS total_rows FROM {self.table}"
            result = self.db_client.execute(query).fetchall()
            logger.info(
                f"Counted {result[0][0]} entries in {self.table} table."
            )
            return result[0][0] if result else None
        except Exception as e:
            logger.error(
                f"Failed to count entries in '{self.table}': {e}"
            )
            return None

    def get_embeddings(self, species: str) -> dict | None:
        """
        Retrieve UMAP embeddings for a given species.
        """
        image_meta_table = ImageMetaConfig().table
        # We trim and replace a space with underscore to match the database format
        species = self.sanitize_species(species)
        try:
            # Construct the SQL query to retrieve UMAP embeddings for the given species
            # The query ranks the UMAP embeddings for each species and cluster label,
            # prioritizing entries with non-null latitude and longitude values.
            query = f"""
                WITH ranked AS (
                    SELECT 
                        a.*,
                        m.lat,
                        m.lon,
                        m.class_dv,
                        ROW_NUMBER() OVER (
                            PARTITION BY a.species, a.cluster_label 
                            ORDER BY 
                                CASE WHEN m.lat IS NOT NULL AND m.lon IS NOT NULL 
                                    THEN 1 ELSE 0 END DESC
                        ) AS row_num
                    FROM {self.table} a
                    JOIN {image_meta_table} m
                    ON a.img_id = REPLACE(m.mask_name, '.png', '')
                    WHERE a.species = ?
                )
                SELECT *
                FROM ranked
                WHERE row_num <= 5
            """
            results = self.db_client.execute_prepared_to_pl(
                query, [species]
            )

            if results.is_empty():
                return None

            results = results.rename(
                {"UMAP1": "umap_x", "UMAP2": "umap_y"}
            ).select(pl.exclude("species", "index"))
            logger.debug(
                f"UMAP query results sample: {results.head(1)}"
            )
            umap = [
                UmapEmbedding.model_validate(row)
                for row in results.to_dicts()
            ]

            # We count the number of clusters by counting the unique cluster labels in the UMAP embeddings
            cluster_counts = len(
                set([embedding.cluster_label for embedding in umap])
            )

            return UmapData.model_validate(
                {
                    "species": species,
                    "cluster_counts": cluster_counts,
                    "umap_embeddings": umap,
                }
            ).model_dump(by_alias=True)
        except Exception as e:
            logger.error(
                f"Failed to retrieve UMAP embeddings for species '{species}': {e}"
            )
            raise e

    def sanitize_species(self, species: str) -> str:
        """
        Sanitize the species name to match the database format.
        """
        return species.lower().strip().replace(" ", "_")
