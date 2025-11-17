from ..configs.config import UmapDataConfig
from ..database.duckdb import DuckDBClient
import logging

logger = logging.getLogger(__name__)


class UmapData:
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
            self.db_client.create_table_if_not_exists(
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
