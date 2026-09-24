import polars as pl
import logging
import uuid

from typing import List

from instharmonize.sources import holder_code_sql

from ..configs.config import (
    ColConfig,
    GbifConfig,
    ImageMetaConfig,
    LepTraitConfig,
    LocalityConfig,
    ProvenanceConfig,
)
from ..database.duckdb import DuckDBClient

logger = logging.getLogger(__name__)

# The occurrence columns every specimen listing returns. Kingdom, phylum,
# class and order are included for callers that need them; the search table
# does not render them.
SPECIMEN_COLUMNS = (
    "img_id",
    "species",
    "family",
    "common_name",
    "sex",
    "life_stage",
    "class_dv",
    "lat",
    "lon",
    "source_db",
    "kingdom",
    "phylum",
    "class",
    "order",
)

# Per-occurrence taxonomic update, joined from the colharmonize run.
SPECIMEN_TAXONOMY_COLUMNS = (
    "update_status",
    "match_method",
    "display_accepted_name",
    "accepted_name",
    "accepted_rank",
    "accepted_authorship",
    "accepted_family",
    "candidate_count",
)

# The written locality, joined out of gbif_meta by LocalityService. lat and
# lon are deliberately absent: image_meta already supplies them, and selecting
# both copies would make an unqualified reference ambiguous.
SPECIMEN_LOCALITY_COLUMNS = (
    "country",
    "country_code",
    "state_province",
    "county",
    "municipality",
    "locality",
    "verbatim_locality",
)

# Coordinate validation, written offline by `geoharmonize integrate`.
SPECIMEN_COORDINATE_COLUMNS = (
    "validation_status",
    "coordinate_check",
    "country_check",
    "adm1_check",
    "reference_country",
    "reference_adm1",
)

# Who holds the specimen and how they number it, from ProvenanceService. The
# institution's full name and website are not joined here: they are keyed on
# the code, not the image, and TextToDbSearch adds them per page.
SPECIMEN_PROVENANCE_COLUMNS = (
    "institution_code",
    "catalog_number",
)

# LepTraits, keyed to the occurrence through its accepted species by
# TraitIndexService. Stored as the words a reader searches with.
SPECIMEN_TRAIT_COLUMNS = (
    "canopy_affinity",
    "edge_affinity",
    "moisture_affinity",
    "disturbance_affinity",
    "voltinism",
    "diapause_stage",
    "oviposition_style",
    "hostplant_families",
    "host_breadth",
    "flight_months",
    "wing_size",
)

# `geoharmonize integrate` keys its output on the logical field it was told
# to read, which is `source_id` whatever column fed it. The backend maps that
# to img_id at the join rather than asking the tool to know our column names.
COORDINATE_KEY_COLUMN = "source_id"

_OCCURRENCE_ALIAS = "occurrence"
_TAXONOMY_ALIAS = "taxonomy"
_LOCALITY_ALIAS = "locality_meta"
_COORDINATE_ALIAS = "coordinates_meta"
_PROVENANCE_ALIAS = "provenance_meta"
_TRAITS_ALIAS = "traits_meta"

# Which joined table owns each searchable column. Anything not listed here
# belongs to image_meta itself.
_FIELD_OWNER = {
    **{name: _TAXONOMY_ALIAS for name in SPECIMEN_TAXONOMY_COLUMNS},
    **{name: _LOCALITY_ALIAS for name in SPECIMEN_LOCALITY_COLUMNS},
    **{name: _COORDINATE_ALIAS for name in SPECIMEN_COORDINATE_COLUMNS},
    **{name: _PROVENANCE_ALIAS for name in SPECIMEN_PROVENANCE_COLUMNS},
    **{name: _TRAITS_ALIAS for name in SPECIMEN_TRAIT_COLUMNS},
}


class ImageMetaStats:
    """Class to handle image persistence operations stats."""

    def __init__(self, duckdb: DuckDBClient):
        config = ImageMetaConfig()
        self.table = config.table
        self.gbif_table = GbifConfig().table
        self.db_client = duckdb

    def get_entries_count(self) -> int | None:
        """Count the number of entries in the image collection."""
        result = self.db_client.execute(
            f"SELECT COUNT(*) AS entries FROM {self.table}"
        ).pl()
        if result.is_empty():
            logger.warning("No entries found in the image collection.")
            return None
        return result["entries"][0]

    def get_family_count(self) -> int | None:
        """Get the number of families in the image collection."""
        result = self.db_client.execute(
            f"SELECT COUNT(DISTINCT family) AS families FROM {self.table}"
        ).pl()
        if result.is_empty():
            logger.warning("No families found in the image collection.")
            return None
        return result["families"][0]

    def get_species_count(self) -> int | None:
        """Get the number of species in the image collection."""
        result = self.db_client.execute(
            f"SELECT COUNT(DISTINCT species) AS species FROM {self.table}"
        ).pl()
        if result.is_empty():
            logger.warning("No species found in the image collection.")
            return None
        return result["species"][0]

    def get_source_db_count(self) -> dict | None:
        """Get the count of images from each source database in the image collection.

        The canonical source databases are 'gbif', 'ecdysis', and 'scanbugs'.
        A record published to more than one of them carries a slash-joined
        value, e.g. 'gbif/scanbugs' -- that is every non-canonical value this
        table has ever had, so those rows are aggregated under 'multiple'
        rather than 'other', which would wrongly suggest a fourth, unnamed
        source.
        """
        result = self.db_client.execute(
            f"SELECT source_db, COUNT(*) AS count FROM {self.table} GROUP BY source_db"
        ).pl()
        if result.is_empty():
            logger.warning("No source databases found in the image collection.")
            return None

        CANONICAL = {"gbif", "ecdysis", "scanbugs"}
        counts: dict[str, int] = {}
        for source_db, count in zip(
            result["source_db"].to_list(), result["count"].to_list()
        ):
            key = source_db if source_db in CANONICAL else "multiple"
            counts[key] = counts.get(key, 0) + count
        return counts

    def get_institution_counts(self) -> dict | None:
        """Get the count of images per holding institution.

        image_meta carries no institution field; it comes from
        gbif_meta.institutionCode (or a name written in institutionID when
        the code is empty; see holder_code_sql), matched on occurrenceID the same way
        LocalityService joins locality fields. gbif_meta has duplicate
        occurrenceID values, so the join is deduplicated the same way: the
        most complete row wins, tie-broken by gbifID for a stable result.

        Records with no GBIF match, or a match with no institution at all,
        are grouped under 'Unknown' rather than dropped, so the proportions
        account for every image.
        """
        if not self.db_client.table_exists(self.gbif_table):
            logger.warning(
                f"No '{self.gbif_table}' table; institution counts are unavailable."
            )
            return None
        holder = holder_code_sql(
            '"institutionCode"',
            '"institutionID"'
            if self.db_client.column_exists(self.gbif_table, "institutionID")
            else None,
        )
        result = self.db_client.execute(
            f"""
            WITH deduped AS (
                SELECT "occurrenceID" AS occurrence_id,
                       {holder} AS institution_code
                FROM {self.gbif_table}
                WHERE nullif(trim("occurrenceID"), '') IS NOT NULL
                QUALIFY row_number() OVER (
                    PARTITION BY "occurrenceID"
                    ORDER BY (institution_code IS NULL), "gbifID"
                ) = 1
            )
            SELECT coalesce(d.institution_code, 'Unknown') AS institution,
                   COUNT(*) AS count
            FROM {self.table} im
            LEFT JOIN deduped d ON d.occurrence_id = nullif(trim(im.uuid), '')
            GROUP BY institution
            ORDER BY count DESC
            """
        ).pl()
        if result.is_empty():
            logger.warning("No institution data found in the image collection.")
            return None
        return dict(zip(result["institution"].to_list(), result["count"].to_list()))

    def count_images_per_family(self) -> dict | None:
        """Get the count of images for each family in the image collection."""
        result = self.db_client.execute(
            f"SELECT family, COUNT(*) AS count FROM {self.table} GROUP BY family"
        ).pl()
        if result.is_empty():
            logger.warning("No families found in the image collection.")
            return None
        return dict(zip(result["family"].to_list(), result["count"].to_list()))

    def get_top_ten_species(self) -> dict | None:
        """Get the top 10 species with the most images in the image collection."""
        result = self.db_client.execute(
            f"SELECT species, COUNT(*) AS count FROM {self.table} GROUP BY species ORDER BY count DESC LIMIT 10"
        ).pl()
        if result.is_empty():
            logger.warning("No species found in the image collection.")
            return None
        return dict(zip(result["species"].to_list(), result["count"].to_list()))


class ImageMetaService:
    """
    Service class for handling image metadata operations.

    :param db_client: An instance of the database client.

    """

    # Class-level defaults so these are always readable, including on an
    # instance built without __init__. Only ever rebound, never mutated.
    _taxonomy_table_present: bool | None = None
    _locality_table_present: bool | None = None
    _coordinates_table_present: bool | None = None
    _provenance_table_present: bool | None = None
    _traits_table_present: bool | None = None
    traits_table = "image_meta_traits"

    def __init__(self, duckdb: DuckDBClient):
        config = ImageMetaConfig()
        self.table = config.table
        self.path = config.path
        self.format = config.format
        self.skip_ingestion = config.skip
        self.taxonomy_table = ColConfig().occurrence_status_table
        locality_config = LocalityConfig()
        self.locality_table = locality_config.table
        self.coordinates_table = locality_config.coordinates_table
        self.provenance_table = ProvenanceConfig().table
        self.traits_table = LepTraitConfig().index_table
        # Resolved lazily and cached; the tables appear at ingestion time.
        self._taxonomy_table_present: bool | None = None
        self._locality_table_present: bool | None = None
        self._coordinates_table_present: bool | None = None
        self._provenance_table_present: bool | None = None
        self._traits_table_present: bool | None = None
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

    def get_image_ids_for_species_list(
        self,
        species_list: List[str],
        *,
        raise_on_error: bool = False,
    ) -> List[str]:
        """
        Return all image IDs belonging to any species in the provided list.

        Uses a temporary table join (consistent with get_species_first_image_ids)
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
            if raise_on_error:
                raise
            return []

    def get_species_first_image_ids(
        self, scientific_names: list[str], *, raise_on_error: bool = False
    ) -> pl.DataFrame | None:
        """
        Retrieve one image ID (the lowest) per species for a list of species.

        Aggregating in DuckDB keeps the result to one row per species; a
        location filter can match thousands of species with many images each.

        :param scientific_names: A list of scientific names of the species.
        :return: A DataFrame with `imgId` and `species` columns, or None on failure.
        """
        try:
            temp_name = f"temp_species_{uuid.uuid4().hex}"
            names_df = pl.DataFrame({"species": scientific_names})

            with self.db_client.lock:
                self.db_client.register(temp_name, names_df)
                query = f"""
                    SELECT
                        MIN(m.img_id) AS imgId,
                        m.species
                    FROM {self.table} m
                    INNER JOIN {temp_name} t
                    ON LOWER(REPLACE(m.species, ' ', '_')) = LOWER(REPLACE(t.species, ' ', '_'))
                    GROUP BY m.species
                """
                try:
                    results = self.db_client.execute(query).pl()
                finally:
                    self.db_client.unregister(temp_name)

            return results
        except Exception as e:
            logger.error(
                f"Error retrieving first image IDs for {len(scientific_names)} species: {e}"
            )
            if raise_on_error:
                raise
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

    def get_image_ids_by_species(
        self,
        scientific_name: str,
        *,
        limit: int = 100,
        offset: int = 0,
        view_order: bool = False,
        raise_on_error: bool = False,
    ) -> list[str]:
        """
        Retrieve a page of image IDs for a given species.

        Pages are cut by image ID so that offset-based paging is stable
        across requests.

        :param scientific_name: The scientific name of the species.
        :param limit: Maximum number of image IDs to return.
        :param offset: Number of image IDs to skip before collecting results.
        :param view_order: Sort the page dorsal first, then ventral, then any
            other view. Only the order within the page changes: the page is
            still cut by image ID, so it holds the same images either way and
            paging stays stable.
        :return: A list of image IDs.
        """
        cleaned_name = self.sanitize_species_name(scientific_name)
        order = (
            """CASE LOWER(class_dv)
                    WHEN 'dorsal' THEN 0 WHEN 'ventral' THEN 1 ELSE 2
                END, img_id"""
            if view_order
            else "img_id"
        )
        try:
            query = f"""
                SELECT img_id FROM (
                    SELECT img_id, class_dv FROM {self.table}
                    WHERE REPLACE(LOWER(species), '_', '') = REPLACE(LOWER(?), '_', '')
                    ORDER BY img_id
                    LIMIT ? OFFSET ?
                ) AS page
                ORDER BY {order}
            """
            results = self.db_client.execute_prepared_to_pl(
                query, [cleaned_name, limit, offset]
            )
            if results is None or results.is_empty():
                return []
            image_ids = results["img_id"].to_list()
            return image_ids
        except Exception as e:
            logger.error(
                f"Error retrieving image IDs for species '{scientific_name}': {e}"
            )
            if raise_on_error:
                raise
            return []

    def get_image_ids_by_genus(
        self,
        genus: str,
        *,
        limit: int = 100,
        raise_on_error: bool = False,
    ) -> list[str]:
        """
        Retrieve up to `limit` image IDs spread across every species of a genus.

        :param genus: A single-word genus name, e.g. "Caligo".
        :param limit: Maximum number of image IDs to return.
        :return: A list of image IDs, empty when the name is not a genus.
        """
        cleaned_genus = genus.strip().lower()
        if not cleaned_genus.isalpha():
            return []
        try:
            # Species are stored as `genus_epithet`; normalizing spaces keeps
            # the match working for either spelling. Ordering by the random
            # image UUID samples across the genus instead of one species.
            query = f"""
                SELECT img_id FROM {self.table}
                WHERE split_part(REPLACE(LOWER(species), ' ', '_'), '_', 1) = ?
                ORDER BY img_id
                LIMIT ?
            """
            results = self.db_client.execute_prepared_to_pl(
                query, [cleaned_genus, limit]
            )
            if results is None or results.is_empty():
                return []
            return results["img_id"].to_list()
        except Exception as e:
            logger.error(f"Error retrieving image IDs for genus '{genus}': {e}")
            if raise_on_error:
                raise
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

    def _taxonomy_available(self) -> bool:
        """Whether the per-occurrence taxonomy table has been built.

        It only exists once a colharmonize run has been loaded, so search has
        to work without it: joining a table that is not there would take the
        whole search endpoint down.
        """
        if self._taxonomy_table_present is None:
            self._taxonomy_table_present = self.db_client.table_exists(
                self.taxonomy_table
            )
        return self._taxonomy_table_present

    def _locality_available(self) -> bool:
        """Whether the locality table has been built.

        Built at startup by LocalityService, and absent on a database whose
        gbif_meta was never ingested.
        """
        if self._locality_table_present is None:
            self._locality_table_present = self.db_client.table_exists(
                self.locality_table
            )
        return self._locality_table_present

    def _coordinates_available(self) -> bool:
        """Whether the coordinate validation table has been written.

        Produced offline by `geoharmonize integrate`; the backend never builds
        it, so it is absent until an operator has run that once.
        """
        if self._coordinates_table_present is None:
            self._coordinates_table_present = self.db_client.table_exists(
                self.coordinates_table
            )
        return self._coordinates_table_present

    def _provenance_available(self) -> bool:
        """Whether the provenance table has been built.

        Built at startup by ProvenanceService, and absent on a database whose
        gbif_meta was never ingested.
        """
        if self._provenance_table_present is None:
            self._provenance_table_present = self.db_client.table_exists(
                self.provenance_table
            )
        return self._provenance_table_present

    def _traits_available(self) -> bool:
        """Whether the trait index has been built.

        Built at startup by TraitIndexService, and absent when LepTraits was
        never ingested.
        """
        if self._traits_table_present is None:
            self._traits_table_present = self.db_client.table_exists(self.traits_table)
        return self._traits_table_present

    def _optional_joins(
        self,
    ) -> tuple[tuple[bool, str, str, str, tuple[str, ...]], ...]:
        """Each optional per-image table: availability, name, alias, key, columns."""
        return (
            (
                self._taxonomy_available(),
                self.taxonomy_table,
                _TAXONOMY_ALIAS,
                "img_id",
                SPECIMEN_TAXONOMY_COLUMNS,
            ),
            (
                self._locality_available(),
                self.locality_table,
                _LOCALITY_ALIAS,
                "img_id",
                SPECIMEN_LOCALITY_COLUMNS,
            ),
            (
                self._coordinates_available(),
                self.coordinates_table,
                _COORDINATE_ALIAS,
                COORDINATE_KEY_COLUMN,
                SPECIMEN_COORDINATE_COLUMNS,
            ),
            (
                self._provenance_available(),
                self.provenance_table,
                _PROVENANCE_ALIAS,
                "img_id",
                SPECIMEN_PROVENANCE_COLUMNS,
            ),
            (
                self._traits_available(),
                self.traits_table,
                _TRAITS_ALIAS,
                "img_id",
                SPECIMEN_TRAIT_COLUMNS,
            ),
        )

    def specimen_source(self) -> str:
        """The FROM clause for a specimen listing.

        Each of the per-image tables is optional and joined only when it
        exists: joining one that is not there would take the whole search
        endpoint down with a catalog error.
        """
        source = f"{self.table} AS {_OCCURRENCE_ALIAS}"
        for available, table, alias, key, _columns in self._optional_joins():
            if not available:
                continue
            source += (
                f"\n            LEFT JOIN {table} AS {alias}"
                f"\n                   ON {alias}.{key} = {_OCCURRENCE_ALIAS}.img_id"
            )
        return source

    def specimen_projection(self) -> str:
        """The SELECT list for a specimen listing.

        Columns from a table that has not been built are selected as NULL, so
        the payload keeps one shape however much has been loaded.
        """
        columns = [f'{_OCCURRENCE_ALIAS}."{name}"' for name in SPECIMEN_COLUMNS]
        for available, _table, alias, _key, names in self._optional_joins():
            if available:
                columns += [f'{alias}."{name}"' for name in names]
            else:
                columns += [f"NULL AS {name}" for name in names]
        return ", ".join(columns)

    def _column_ref(self, field: str) -> str:
        """How to refer to a searchable field in a WHERE clause.

        Qualified by the table that owns it, because three of the four tables
        are optional. When the owner is absent the reference becomes a typed
        NULL, so a targeted search on, say, `country` before the locality table
        exists returns nothing rather than failing the request: an unqualified
        name for a column that is not in the catalog is a binder error, and it
        takes the whole endpoint down with it.
        """
        alias = _FIELD_OWNER.get(field)
        if alias is None:
            return f'{_OCCURRENCE_ALIAS}."{field}"'
        available = {
            _TAXONOMY_ALIAS: self._taxonomy_available,
            _LOCALITY_ALIAS: self._locality_available,
            _COORDINATE_ALIAS: self._coordinates_available,
            _PROVENANCE_ALIAS: self._provenance_available,
            _TRAITS_ALIAS: self._traits_available,
        }[alias]
        if not available():
            return "CAST(NULL AS VARCHAR)"
        return f'{alias}."{field}"'

    def search_by_coordinate(
        self,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float,
        limit: int,
        offset: int,
    ) -> tuple[pl.DataFrame, pl.DataFrame, int]:
        """Search metadata by geographic coordinate bounding box."""
        query = f"""
            SELECT
                LOWER(REPLACE(species, ' ', '_')) AS species_key,
                FIRST(species) AS species,
                bool_or(TRUE) AS match_field
            FROM {self.specimen_source()}
            WHERE lat BETWEEN ? AND ?
              AND lon BETWEEN ? AND ?
            GROUP BY species_key
        """
        params = [lat_min, lat_max, lon_min, lon_max]
        results_df = self.db_client.execute_prepared_to_pl(query, params)

        specimen_query = f"""
            SELECT {self.specimen_projection()}
            FROM {self.specimen_source()}
            WHERE lat BETWEEN ? AND ?
              AND lon BETWEEN ? AND ?
            LIMIT ? OFFSET ?
        """
        specimen_params = [lat_min, lat_max, lon_min, lon_max, limit, offset]
        specimens_df = self.db_client.execute_prepared_to_pl(
            specimen_query, specimen_params
        )

        count_query = f"""
            SELECT COUNT(*)
            FROM {self.specimen_source()}
            WHERE lat BETWEEN ? AND ?
              AND lon BETWEEN ? AND ?
        """
        count_params = [lat_min, lat_max, lon_min, lon_max]
        count_df = self.db_client.execute_prepared_to_pl(count_query, count_params)
        total_specimens = count_df[0, 0] if not count_df.is_empty() else 0

        return results_df, specimens_df, total_specimens

    def search_by_field(
        self, field: str, q_param: str, limit: int, offset: int
    ) -> tuple[pl.DataFrame, pl.DataFrame, int]:
        """Search metadata by a specific field.

        `limit` and `offset` page the specimens only. The species list is
        every match, so the results page can list them all whatever specimen
        page the reader is on; the same holds for the other two searches.
        """
        col_name = self._column_ref(field)

        query = f"""
            SELECT
                LOWER(REPLACE(species, ' ', '_')) AS species_key,
                FIRST(species) AS species,
                bool_or(REPLACE({col_name}, '_', ' ') ILIKE ?) AS match_field
            FROM {self.specimen_source()}
            WHERE REPLACE({col_name}, '_', ' ') ILIKE ?
            GROUP BY species_key
        """
        params = [q_param, q_param]
        results_df = self.db_client.execute_prepared_to_pl(query, params)

        specimen_query = f"""
            SELECT {self.specimen_projection()}
            FROM {self.specimen_source()}
            WHERE REPLACE({col_name}, '_', ' ') ILIKE ?
            LIMIT ? OFFSET ?
        """
        specimen_params = [q_param, limit, offset]
        specimens_df = self.db_client.execute_prepared_to_pl(
            specimen_query, specimen_params
        )

        count_query = f"""
            SELECT COUNT(*)
            FROM {self.specimen_source()}
            WHERE REPLACE({col_name}, '_', ' ') ILIKE ?
        """
        count_params = [q_param]
        count_df = self.db_client.execute_prepared_to_pl(count_query, count_params)
        total_specimens = count_df[0, 0] if not count_df.is_empty() else 0

        return results_df, specimens_df, total_specimens

    def search_all_fields(
        self, search_fields: list[str], q_param: str, limit: int, offset: int
    ) -> tuple[pl.DataFrame, pl.DataFrame, int]:
        """Search metadata across all valid fields."""
        conditions = []
        selects = []
        params = []

        for col in search_fields:
            col_esc = self._column_ref(col)
            conditions.append(f"REPLACE({col_esc}, '_', ' ') ILIKE ?")
            selects.append(
                f"bool_or(REPLACE({col_esc}, '_', ' ') ILIKE ?) AS match_{col}"
            )
            params.append(q_param)

        params.extend([q_param] * len(search_fields))

        selects_str = ", ".join(selects)
        conditions_str = " OR ".join(conditions)

        query = f"""
            SELECT
                LOWER(REPLACE(species, ' ', '_')) AS species_key,
                FIRST(species) AS species,
                {selects_str}
            FROM {self.specimen_source()}
            WHERE {conditions_str}
            GROUP BY species_key
        """
        results_df = self.db_client.execute_prepared_to_pl(query, params)

        specimen_query = f"""
            SELECT {self.specimen_projection()}
            FROM {self.specimen_source()}
            WHERE {conditions_str}
            LIMIT ? OFFSET ?
        """
        specimen_params = [q_param] * len(search_fields) + [limit, offset]
        specimens_df = self.db_client.execute_prepared_to_pl(
            specimen_query, specimen_params
        )

        count_query = f"""
            SELECT COUNT(*)
            FROM {self.specimen_source()}
            WHERE {conditions_str}
        """
        count_params = [q_param] * len(search_fields)
        count_df = self.db_client.execute_prepared_to_pl(count_query, count_params)
        total_specimens = count_df[0, 0] if not count_df.is_empty() else 0

        return results_df, specimens_df, total_specimens
