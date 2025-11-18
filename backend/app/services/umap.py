from ..database.model import UmapEmbedding, UmapData
from ..configs.config import UmapDataConfig
from ..database.duckdb import DuckDBClient
import polars as pl
import logging

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

    def get_embeddings(self, species: str) -> dict:
        """
        Retrieve UMAP embeddings for a given species.
        """
        # We trim and replace a space with underscore to match the database format
        species = species.strip().replace(" ", "_")
        try:
            query = f"SELECT * FROM {self.table} WHERE species = LOWER('{species}')"
            results = self.db_client.execute(query).pl()

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

            return UmapData.model_validate(
                {"species": species, "umap_embeddings": umap}
            ).model_dump(by_alias=True)
        except Exception as e:
            logger.error(
                f"Failed to retrieve UMAP embeddings for species '{species}': {e}"
            )
            raise e
