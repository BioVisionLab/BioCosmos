import polars as pl
import logging
import uuid

from typing import List

from ..configs.config import ImageMetaConfig
from ..database.duckdb import DuckDBClient

logger = logging.getLogger(__name__)


class ImageMetaStats:
    """Class to handle image persistence operations stats."""

    def __init__(self, duckdb: DuckDBClient):
        config = ImageMetaConfig()
        self.table = config.table
        self.db_client = duckdb

    def get_entries_count(self) -> int | None:
        """Count the number of entries in the image collection."""
        result = self.db_client.execute(f"SELECT COUNT(*) AS entries FROM {self.table}").pl()
        if result.is_empty():
            logger.warning("No entries found in the image collection.")
            return None
        return result["entries"][0]

    def get_family_count(self) -> int | None:
        """Get the number of families in the image collection."""
        result = self.db_client.execute(f"SELECT COUNT(DISTINCT family) AS families FROM {self.table}").pl()
        if result.is_empty():
            logger.warning("No families found in the image collection.")
            return None
        return result["families"][0]

    def get_species_count(self) -> int | None:
        """Get the number of species in the image collection."""
        result = self.db_client.execute(f"SELECT COUNT(DISTINCT species) AS species FROM {self.table}").pl()
        if result.is_empty():
            logger.warning("No species found in the image collection.")
            return None
        return result["species"][0]

    def get_source_db_count(self) -> dict | None:
        """Get the count of images from each source database in the image collection.

        The canonical source databases are 'gbif', 'ecdysis', and 'scanbugs'.
        Any other source_db value is aggregated under the key 'other'.
        """
        result = self.db_client.execute(
            f"SELECT source_db, COUNT(*) AS count FROM {self.table} GROUP BY source_db"
        ).pl()
        if result.is_empty():
            logger.warning("No source databases found in the image collection.")
            return None

        CANONICAL = {"gbif", "ecdysis", "scanbugs"}
        counts: dict[str, int] = {}
        for source_db, count in zip(result["source_db"].to_list(), result["count"].to_list()):
            key = source_db if source_db in CANONICAL else "other"
            counts[key] = counts.get(key, 0) + count
        return counts


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
            
            # Create a full-text search index on relevant metadata columns
            self._index_columns()
        except Exception as e:
            logger.error(f"Failed to ingest image metadata into '{self.table}': {e}")
            raise e

    def _index_columns(self):
        """
        Create a full-text search index on relevant columns of the metadata table.
        """
        try:
            IMAGE_META_COLUMNS_INDEXED = [
                "class_dv",
                "tax_rank",
                "tax_status",
                "family",
                "species",
                "sex",
                "life_stage",
                "lat",
                "lon",
                "source_db",
                "kingdom",
                "phylum",
                "class",
                "order",
                "common_name",
            ]
            self.db_client.index_table(
                table_name=self.table,
                id_column="rowid",
                columns=IMAGE_META_COLUMNS_INDEXED,
                overwrite=True,
            )
            logger.info("Full-text search index created on image metadata table.")
        except Exception as e:
            logger.error(f"Failed to create full-text search index on image metadata table: {e}")
            raise

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


    def search_by_coordinate(self, lat_min: float, lat_max: float, lon_min: float, lon_max: float, limit: int, offset: int) -> tuple[pl.DataFrame, pl.DataFrame, int]:
        """Search metadata by geographic coordinate bounding box."""
        query = f"""
            SELECT
                LOWER(REPLACE(species, ' ', '_')) AS species_key,
                FIRST(species) AS species,
                bool_or(TRUE) AS match_field
            FROM {self.table}
            WHERE lat BETWEEN ? AND ?
              AND lon BETWEEN ? AND ?
            GROUP BY species_key
            LIMIT ?
        """
        params = [lat_min, lat_max, lon_min, lon_max, limit]
        results_df = self.db_client.execute_prepared_to_pl(query, params)

        specimen_query = f"""
            SELECT img_id, species, family, common_name, sex, life_stage, class_dv, lat, lon, source_db, kingdom, phylum, class, "order"
            FROM {self.table}
            WHERE lat BETWEEN ? AND ?
              AND lon BETWEEN ? AND ?
            LIMIT ? OFFSET ?
        """
        specimen_params = [lat_min, lat_max, lon_min, lon_max, limit, offset]
        specimens_df = self.db_client.execute_prepared_to_pl(specimen_query, specimen_params)

        count_query = f"""
            SELECT COUNT(*)
            FROM {self.table}
            WHERE lat BETWEEN ? AND ?
              AND lon BETWEEN ? AND ?
        """
        count_params = [lat_min, lat_max, lon_min, lon_max]
        count_df = self.db_client.execute_prepared_to_pl(count_query, count_params)
        total_specimens = count_df[0, 0] if not count_df.is_empty() else 0

        return results_df, specimens_df, total_specimens

    def search_by_field(self, field: str, q_param: str, limit: int, offset: int) -> tuple[pl.DataFrame, pl.DataFrame, int]:
        """Search metadata by a specific field."""
        col_name = f'"{field}"'
        
        query = f"""
            SELECT
                LOWER(REPLACE(species, ' ', '_')) AS species_key,
                FIRST(species) AS species,
                bool_or(REPLACE({col_name}, '_', ' ') ILIKE ?) AS match_field
            FROM {self.table}
            WHERE REPLACE({col_name}, '_', ' ') ILIKE ?
            GROUP BY species_key
            LIMIT ?
        """
        params = [q_param, q_param, limit]
        results_df = self.db_client.execute_prepared_to_pl(query, params)

        specimen_query = f"""
            SELECT img_id, species, family, common_name, sex, life_stage, class_dv, lat, lon, source_db, kingdom, phylum, class, "order"
            FROM {self.table}
            WHERE REPLACE({col_name}, '_', ' ') ILIKE ?
            LIMIT ? OFFSET ?
        """
        specimen_params = [q_param, limit, offset]
        specimens_df = self.db_client.execute_prepared_to_pl(specimen_query, specimen_params)

        count_query = f"""
            SELECT COUNT(*)
            FROM {self.table}
            WHERE REPLACE({col_name}, '_', ' ') ILIKE ?
        """
        count_params = [q_param]
        count_df = self.db_client.execute_prepared_to_pl(count_query, count_params)
        total_specimens = count_df[0, 0] if not count_df.is_empty() else 0

        return results_df, specimens_df, total_specimens

    def search_all_fields(self, search_fields: list[str], q_param: str, limit: int, offset: int) -> tuple[pl.DataFrame, pl.DataFrame, int]:
        """Search metadata across all valid fields."""
        conditions = []
        selects = []
        params = []
        
        for col in search_fields:
            col_esc = f'"{col}"'
            conditions.append(f"REPLACE({col_esc}, '_', ' ') ILIKE ?")
            selects.append(f"bool_or(REPLACE({col_esc}, '_', ' ') ILIKE ?) AS match_{col}")
            params.append(q_param)
        
        params.extend([q_param] * len(search_fields))
        params.append(limit)
        
        selects_str = ", ".join(selects)
        conditions_str = " OR ".join(conditions)
        
        query = f"""
            SELECT
                LOWER(REPLACE(species, ' ', '_')) AS species_key,
                FIRST(species) AS species,
                {selects_str}
            FROM {self.table}
            WHERE {conditions_str}
            GROUP BY species_key
            LIMIT ?
        """
        results_df = self.db_client.execute_prepared_to_pl(query, params)

        specimen_query = f"""
            SELECT img_id, species, family, common_name, sex, life_stage, class_dv, lat, lon, source_db, kingdom, phylum, class, "order"
            FROM {self.table}
            WHERE {conditions_str}
            LIMIT ? OFFSET ?
        """
        specimen_params = [q_param] * len(search_fields) + [limit, offset]
        specimens_df = self.db_client.execute_prepared_to_pl(specimen_query, specimen_params)

        count_query = f"""
            SELECT COUNT(*)
            FROM {self.table}
            WHERE {conditions_str}
        """
        count_params = [q_param] * len(search_fields)
        count_df = self.db_client.execute_prepared_to_pl(count_query, count_params)
        total_specimens = count_df[0, 0] if not count_df.is_empty() else 0

        return results_df, specimens_df, total_specimens
