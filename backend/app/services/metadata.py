import polars as pl
import logging
import uuid

from typing import List

from ..configs.config import ImageMetaConfig
from ..database.duckdb import DuckDBClient

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
        self.format = config.format
        self.skip_ingestion = config.skip
        self.db_client = duckdb

    def ingest(self):
        """
        Ingest image metadata into the database.
        """
        if self.skip_ingestion:
            logger.info("Skipping image metadata ingestion as per configuration.")
            return
        try:
            if self.format == "csv":
                self.db_client.create_or_replace_table_csv(
                    table_name=self.table, csv_path=self.path
                )
            elif self.format == "parquet":
                self.db_client.create_or_replace_parquet(
                    table_name=self.table, parquet_path=self.path
                )
            else:
                raise ValueError(f"Unsupported format: {self.format}")
        except Exception as e:
            logger.error(f"Failed to ingest image metadata into '{self.table}': {e}")
            raise e

    def get_image_count_by_species(self, scientific_name: str) -> int | None:
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
            result = self.db_client.execute_query(query, cleaned_name).pl()
            count = result["image_count"][0] if not result.is_empty() else 0
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
            # Register species list as a temp table with unique name ? avoids SQL injection and concurrency deadlocks
            temp_name = f"temp_species_ids_{uuid.uuid4().hex}"
            names_df = pl.DataFrame({"species": species_list})
            
            with self.db_client.lock:
                self.db_client.register(temp_name, names_df)
                query = f"""
                    SELECT img_id
                    FROM {self.table} m
                    INNER JOIN {temp_name} t
                    ON LOWER(REPLACE(m.species, ' ', '_')) = LOWER(REPLACE(t.species, ' ', '_'))
                """
                try:
                    result = self.db_client.execute(query).pl()
                finally:
                    self.db_client.unregister(temp_name)

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
            # Create a temporary table with the species names using unique identifier
            temp_name = f"temp_species_{uuid.uuid4().hex}"
            names_df = pl.DataFrame({"species": scientific_names})
            
            with self.db_client.lock:
                self.db_client.register(temp_name, names_df)
                query = f"""
                    SELECT 
                        m.img_id AS imgId,
                        m.species
                    FROM {self.table} m
                    INNER JOIN {temp_name} t 
                    ON LOWER(REPLACE(m.species, ' ', '_')) = LOWER(REPLACE(t.species, ' ', '_'))
                """
                try:
                    results = self.db_client.execute(query).pl()
                finally:
                    self.db_client.unregister(temp_name)

            return results
        except Exception as e:
            logger.error(
                f"Error retrieving main image IDs for species list '{scientific_names}': {e}"
            )
            return None

    def get_species_main_image_id(self, scientific_name: str) -> str | None:
        """
        Retrieve the main image ID for a given species.

        :param scientific_name: The scientific name of the species.
        :return: The main image ID or None if not found.
        """
        cleaned_name = self.sanitize_species_name(scientific_name)
        try:
            query = f"""
                SELECT img_id FROM {self.table}
                WHERE REPLACE(LOWER(species), '_', '') = REPLACE(LOWER(?), '_', '')
                LIMIT 1
            """
            results = self.db_client.execute_query(query, cleaned_name).pl()
            if not results.is_empty():
                return results["img_id"][0]
            return None
        except Exception as e:
            logger.error(
                f"Error retrieving main image ID for species '{scientific_name}': {e}"
            )
            return None

    def get_image_ids_by_species(self, scientific_name: str) -> list[str]:
        """
        Retrieve image IDs for a given species.

        :param scientific_name: The scientific name of the species.
        :return: A list of image IDs.
        """
        cleaned_name = self.sanitize_species_name(scientific_name)
        try:
            query = f"""
                SELECT img_id FROM {self.table}
                WHERE REPLACE(LOWER(species), '_', '') = REPLACE(LOWER(?), '_', '')
                LIMIT 100
            """
            results = self.db_client.execute_query(query, cleaned_name).pl()
            image_ids = results["img_id"].to_list()
            return image_ids
        except Exception as e:
            logger.error(
                f"Error retrieving image IDs for species '{scientific_name}': {e}"
            )
            return []

    def get_image_meta_by_species(self, species: str) -> pl.DataFrame | None:
        """
        Retrieve image IDs for a given species.

        :param species: The species name to filter image IDs.
        :return: A list of image IDs or None if an error occurs.
        """
        cleaned_species = self.sanitize_species_name(species)
        try:
            query = f"""
                SELECT img_id, species, source_db, class_dv FROM {self.table}
                WHERE REPLACE(LOWER(species), '_', '') = REPLACE(LOWER(?), '_', '') LIMIT 100
            """
            # We export result to polars for easier handling
            results = self.db_client.execute_query(query, cleaned_species).pl()
            return results
        except Exception as e:
            logger.error(f"Error retrieving image IDs for species '{species}': {e}")
            return None

    def get_meta_by_image_ids(self, img_ids: list[str]) -> pl.DataFrame | None:
        try:
            if not img_ids:
                logger.warning("No image IDs provided.")
                return pl.DataFrame()

            # Create a temporary table with the IDs using unique identifier
            temp_name = f"temp_ids_{uuid.uuid4().hex}"
            ids_df = pl.DataFrame({"img_id": img_ids})
            
            with self.db_client.lock:
                self.db_client.register(temp_name, ids_df)
                query = f"""
                    SELECT img_id, m.species, m.source_db, m.class_dv 
                    FROM {self.table} m
                    INNER JOIN {temp_name} t ON m.mask_name = t.img_id
                """
                try:
                    duckdb_results = self.db_client.execute(query).pl()
                finally:
                    self.db_client.unregister(temp_name)

            return duckdb_results

        except Exception as e:
            logger.error(f"Error retrieving metadata for image IDs '{img_ids}': {e}")
            return None

    def get_meta_by_image_id(self, img_id: str) -> pl.DataFrame | None:
        """
        Retrieve metadata for a single image ID.

        :param img_id: The image identifier (without or with .png).
        :return: A Polars DataFrame with a single row of metadata or None if not found.
        """
        try:
            cleaned_id = img_id.replace(".png", "")
            query = f"""
                SELECT * FROM {self.table}
                WHERE img_id = ?
                LIMIT 1
            """
            result = self.db_client.execute_query(query, cleaned_id).pl()
            if result is None or result.is_empty():
                return None
            return result
        except Exception as e:
            logger.error(f"Error retrieving metadata for image ID '{img_id}': {e}")
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
                logger.warning("No image data to merge with metadata.")
                return None

            # Register the full image_data DataFrame as a temporary table using unique identifier
            temp_name = f"temp_image_data_{uuid.uuid4().hex}"
            
            with self.db_client.lock:
                self.db_client.register(temp_name, image_data)
                query = f"""
                    SELECT 
                        t.*,
                        m.species,
                        m.source_db,
                        m.class_dv
                    FROM {temp_name} t
                    INNER JOIN {self.table} m ON t.imgId = m.img_id
                """
                try:
                    merged_results = self.db_client.execute(query).pl()
                finally:
                    self.db_client.unregister(temp_name)

            if merged_results is None or merged_results.is_empty():
                logger.warning("No metadata found for the given image IDs.")
                return None

            return merged_results

        except Exception as e:
            logger.error(f"Error merging metadata with image data: {e}")
            return None

    def check_species_exists(self, species: list[str]) -> list[str]:
        """
        Check if the given species exist in the image metadata table.

        :param species: A list of species names to check.
        :return: A list of cleaned species names (lowercase, underscores) that
                exist in the metadata table.
        """
        if not species:
            return []

        try:
            cleaned_species = [self.sanitize_species_name(s) for s in species]
            placeholders = ", ".join(["?"] * len(cleaned_species))
            query = f"""
                SELECT DISTINCT REPLACE(LOWER(species), ' ', '_') AS cleaned_species
                FROM {self.table}
                WHERE REPLACE(LOWER(species), ' ', '_') IN ({placeholders})
            """
            results = self.db_client.execute_prepared(
                query, params=cleaned_species
            ).pl()
            return (
                results["cleaned_species"].to_list() if not results.is_empty() else []
            )

        except Exception as e:
            logger.error(f"Error checking species existence: {e}")
            return []

    def sanitize_species_name(self, species: str) -> str:
        """
        Sanitize the species name for consistent querying.

        :param species: The original species name.
        :return: The sanitized species name.
        """
        return species.strip().lower().replace(" ", "_")
