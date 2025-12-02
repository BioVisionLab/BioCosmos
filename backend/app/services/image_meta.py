from ..database.model import ImageMetadata
from ..configs.config import ImageMetaConfig
from ..database.duckdb import DuckDBClient
import logging

logger = logging.getLogger(__name__)


class ImageMetaService:
    """
    Service class for handling image metadata operations.

    :param db_client: An instance of the database client.

    """

    def __init__(self, duckdb: DuckDBClient):
        config = ImageMetaConfig()
        self.table = config.table
        self.path = config.path
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
            self.db_client.create_or_replace_table_csv(
                table_name=self.table, csv_path=self.path
            )
            # entries: int | None = self.count_entries()
            # if entries is not None:
            #     logger.info(
            #         f"Image metadata ingested successfully from '{self.path}'."
            #     )
            #     logger.info(
            #         f"Total entries after ingestion: {entries}"
            #     )
        except Exception as e:
            logger.error(
                f"Failed to ingest image metadata into '{self.table}': {e}"
            )
            raise e

    # def count_entries(self) -> int | None:
    #     """
    #     Count the number of entries in the image metadata table.

    #     :return: The count of entries or None if an error occurs.
    #     """
    #     try:
    #         query = f"SELECT COUNT(*) FROM {self.table}"
    #         result = self.db_client.execute(query)
    #         count = result[0][0] if result else 0
    #         return count
    #     except Exception as e:
    #         logger.error(
    #             f"Error counting entries in table '{self.table}': {e}"
    #         )
    #         return None

    def get_image_meta_by_species(
        self, species: str
    ) -> list[ImageMetadata] | None:
        """
        Retrieve image IDs for a given species.

        :param species: The species name to filter image IDs.
        :return: A list of image IDs or None if an error occurs.
        """
        cleaned_species = self.sanitize_species_name(species)
        try:
            query = f"""
                SELECT img_id FROM {self.table}
                WHERE species = '{cleaned_species}'
            """
            results = self.db_client.execute_query(query)
            image_meta_list = [ImageMetadata(*row) for row in results]
            return image_meta_list
        except Exception as e:
            logger.error(
                f"Error retrieving image IDs for species '{species}': {e}"
            )
            return None

    def sanitize_species_name(self, species: str) -> str:
        """
        Sanitize the species name for consistent querying.

        :param species: The original species name.
        :return: The sanitized species name.
        """
        return species.strip().lower().replace(" ", "_")
