import csv
from venv import logger
from ..configs.config import ImageMetaConfig
from ..app.database.duckdb import DuckDBClient
import logging

logger = logging.getLogger(__name__)


class ImageMeta:
    """
    Service class for handling image metadata operations.

    :param db_client: An instance of the database client.

    """

    def __init__(self, duckdb: DuckDBClient):
        config = ImageMetaConfig()
        self.table = config.table
        self.pa = config.path
        self.skip_ingestion = config.skip
        self.db_client = duckdb

    def ingest(self):
        """
        Ingest image metadata into the database.
        """
        if self.skip_ingestion:
            logger.info(
                "Skipping image metadata ingestion as per configuration."
            )
            return
        try:
            self.db_client.create_table_if_not_exists(
                table_name=self.table, csv_path=self.path
            )
            entries: int | None = self.count_entries()
            if entries is not None:
                logger.info(
                    f"Image metadata ingested successfully from '{self.path}'."
                )
                logger.info(
                    f"Total entries after ingestion: {entries}"
                )
        except Exception as e:
            logger.error(
                f"Failed to ingest image metadata into '{self.table}': {e}"
            )
            raise e
