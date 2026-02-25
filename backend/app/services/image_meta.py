import polars as pl
from typing import List
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

    def get_image_count_by_species(
        self, scientific_name: str
    ) -> int | None:
        """
        Retrieve the count of images for a given species.

        :param scientific_name: The scientific name of the species.
        :return: The count of images or None if an error occurs.
        """
        cleaned_name = self.sanitize_species_name(scientific_name)
        try:
            query = f"""
                SELECT COUNT(*) AS image_count FROM {self.table}
                WHERE REPLACE(LOWER(species), '_', '') = REPLACE(LOWER(?), '_', '')
            """
            result = self.db_client.execute_query(
                query, cleaned_name
            ).pl()
            count = (
                result["image_count"][0]
                if not result.is_empty()
                else 0
            )
            return count
        except Exception as e:
            logger.error(
                f"Error retrieving image count for species '{scientific_name}': {e}"
            )
            return None

    def get_image_ids_for_species_list(self, species_list: List[str]) -> List[str]:
        """
        Return all image IDs belonging to any species in the provided list.

        Uses a temporary table join (consistent with get_species_main_image_id_from_list)
        to avoid SQL injection and handle large species lists safely.

        Args:
            species_list: List of scientific species names

        Returns:
            List of image ID strings (without .png extension), empty list on failure
        """
        if not species_list:
            return []

        try:
            # Register species list as a temp table ? avoids SQL injection
            names_df = pl.DataFrame({"species": species_list})
            self.db_client.register("temp_species_ids", names_df)

            query = f"""
                SELECT REPLACE(m.mask_name, '.png', '') AS img_id
                FROM {self.table} m
                INNER JOIN temp_species_ids t
                ON LOWER(REPLACE(m.species, ' ', '_')) = LOWER(REPLACE(t.species, ' ', '_'))
            """

            result = self.db_client.execute(query).pl()
            self.db_client.unregister("temp_species_ids")

            if result is None or result.is_empty():
                logger.warning(
                    f"No image IDs found for {len(species_list)} species in allowlist."
                )
                return []

            return result["img_id"].to_list()

        except Exception as e:
            logger.error(
                f"Error retrieving image IDs for species list: {e}",
                exc_info=True,
            )
            return []

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
    def get_species_main_image_id_from_list(
        self, scientific_names: list[str]
    ) -> pl.DataFrame | None:
        """
        Retrieve the main image IDs for a list of species.

        :param scientific_names: A list of scientific names of the species.
        :return: A dictionary mapping species names to their main image IDs or None if not found.
        """
        # We use duck directly to handle multiple species in one query
        try:
            # Create a temporary table with the species names
            names_df = pl.DataFrame({"species": scientific_names})
            self.db_client.register("temp_species", names_df)

            query = f"""
                SELECT 
                    REPLACE(m.mask_name, '.png', '') AS img_id,
                    m.species
                FROM {self.table} m
                INNER JOIN temp_species t 
                ON LOWER(REPLACE(m.species, ' ', '_')) = LOWER(REPLACE(t.species, ' ', '_'))
            """

            results = self.db_client.execute(query).pl()
            self.db_client.unregister("temp_species")

            return results
        except Exception as e:
            logger.error(
                f"Error retrieving main image IDs for species list '{scientific_names}': {e}"
            )
            return None

    def get_species_main_image_id(
        self, scientific_name: str
    ) -> str | None:
        """
        Retrieve the main image ID for a given species.

        :param scientific_name: The scientific name of the species.
        :return: The main image ID or None if not found.
        """
        cleaned_name = self.sanitize_species_name(scientific_name)
        try:
            query = f"""
                SELECT REPLACE(mask_name, '.png', '') AS img_id FROM {self.table}
                WHERE REPLACE(LOWER(species), '_', '') = REPLACE(LOWER(?), '_', '')
                LIMIT 1
            """
            results = self.db_client.execute_query(
                query, cleaned_name
            ).pl()
            if not results.is_empty():
                return results["img_id"][0]
            return None
        except Exception as e:
            logger.error(
                f"Error retrieving main image ID for species '{scientific_name}': {e}"
            )
            return None

    def get_image_ids_by_species(
        self, scientific_name: str
    ) -> list[str]:
        """
        Retrieve image IDs for a given species.

        :param scientific_name: The scientific name of the species.
        :return: A list of image IDs.
        """
        cleaned_name = self.sanitize_species_name(scientific_name)
        try:
            query = f"""
                SELECT REPLACE(mask_name, '.png', '') AS img_id FROM {self.table}
                WHERE REPLACE(LOWER(species), '_', '') = REPLACE(LOWER(?), '_', '')
                LIMIT 100
            """
            results = self.db_client.execute_query(
                query, cleaned_name
            ).pl()
            image_ids = results["img_id"].to_list()
            return image_ids
        except Exception as e:
            logger.error(
                f"Error retrieving image IDs for species '{scientific_name}': {e}"
            )
            return []

    def get_image_meta_by_species(
        self, species: str
    ) -> pl.DataFrame | None:
        """
        Retrieve image IDs for a given species.

        :param species: The species name to filter image IDs.
        :return: A list of image IDs or None if an error occurs.
        """
        cleaned_species = self.sanitize_species_name(species)
        try:
            query = f"""
                SELECT REPLACE(mask_name, '.png', '') AS img_id, species, source_db, class_dv FROM {self.table}
                WHERE REPLACE(LOWER(species), '_', '') = REPLACE(LOWER(?), '_', '') LIMIT 100
            """
            # We export result to polars for easier handling
            results = self.db_client.execute_query(
                query, cleaned_species
            ).pl()
            return results
        except Exception as e:
            logger.error(
                f"Error retrieving image IDs for species '{species}': {e}"
            )
            return None

    def get_meta_by_image_ids(
        self, img_ids: list[str]
    ) -> pl.DataFrame | None:
        try:
            if not img_ids:
                logger.warning("No image IDs provided.")
                return pl.DataFrame()

            # Create a temporary table with the IDs
            ids_df = pl.DataFrame({"img_id": img_ids})
            self.db_client.register("temp_ids", ids_df)

            query = f"""
                SELECT m.mask_name AS img_id, m.species, m.source_db, m.class_dv 
                FROM {self.table} m
                INNER JOIN temp_ids t ON m.mask_name = t.img_id
            """

            duckdb_results = self.db_client.execute(query).pl()
            self.db_client.unregister("temp_ids")

            return duckdb_results

        except Exception as e:
            logger.error(
                f"Error retrieving metadata for image IDs '{img_ids}': {e}"
            )
            return None

    def get_meta_by_image_id(
        self, img_id: str
    ) -> pl.DataFrame | None:
        """
        Retrieve metadata for a single image ID.

        :param img_id: The image identifier (without or with .png).
        :return: A Polars DataFrame with a single row of metadata or None if not found.
        """
        try:
            cleaned_id = img_id.replace(".png", "")
            query = f"""
                SELECT * FROM {self.table}
                WHERE REPLACE(mask_name, '.png', '') = ?
                LIMIT 1
            """
            result = self.db_client.execute_query(query, cleaned_id).pl()
            if result is None or result.is_empty():
                return None
            return result
        except Exception as e:
            logger.error(
                f"Error retrieving metadata for image ID '{img_id}': {e}"
            )
            return None

    def merge_meta_with_image_data(
        self, image_data: pl.DataFrame
    ) -> pl.DataFrame | None:
        """
        Merge image metadata with image data DataFrame.
        :param image_data: The polars DataFrame containing image data.
        :return: Merged polars DataFrame or None if an error occurs.
        """
        try:
            if image_data is None:
                logger.warning(
                    "No image data to merge with metadata."
                )
                return None

            # Register the full image_data DataFrame as a temporary table
            self.db_client.register("temp_image_data", image_data)

            # Perform inner join directly in DuckDB with all columns
            query = f"""
                SELECT 
                    t.*,
                    m.species,
                    m.source_db,
                    m.class_dv
                FROM temp_image_data t
                INNER JOIN {self.table} m ON t.imgId = REPLACE(m.mask_name, '.png', '')
            """

            merged_results = self.db_client.execute(query).pl()
            self.db_client.unregister("temp_image_data")

            if merged_results is None or merged_results.is_empty():
                logger.warning(
                    "No metadata found for the given image IDs."
                )
                return None

            return merged_results

        except Exception as e:
            logger.error(
                f"Error merging metadata with image data: {e}"
            )
            return None

    def sanitize_species_name(self, species: str) -> str:
        """
        Sanitize the species name for consistent querying.

        :param species: The original species name.
        :return: The sanitized species name.
        """
        return species.strip().lower().replace(" ", "_")
