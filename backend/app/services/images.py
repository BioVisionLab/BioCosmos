import numpy as np
import io

from pydantic import BaseModel
from fastapi import Request
from typing import List

from ..services.image_meta import ImageMetaService

from ..database.duckdb import DuckDBClient

from ..configs.config import ImageConfig
from ..database.model import LanceSchema
from ..database.lance import LanceDB
from .unicom import UnicomImageEmbedder
import polars as pl

from .clip import ClipEmbedder
import logging

logger = logging.getLogger(__name__)

# Similarity search is based on LanceDB options:
# https://lancedb.github.io/lancedb/search


class SpeciesImage(BaseModel):
    """Class to represent species image data."""

    species: str
    imageIds: list[str]

    def to_dict(self) -> dict:
        return {
            "species": self.species,
            "imageIds": self.imageIds,
        }


class ImagePersistData:
    """Class to handle image persistence operations."""

    def __init__(self, lance_db: LanceDB, duckdb: DuckDBClient):
        self.config = ImageConfig()
        self.logger = logging.getLogger(__name__)
        self.db_table = lance_db.create_or_get_collection(self.config.table)
        self.meta_table = duckdb

    def entries(self) -> int | None:
        """Count the number of entries in the image collection."""
        result = LanceDB().count_entries(self.config.table)
        if result is None:
            logger.warning("No entries found in the image collection.")
            return None
        return result

    def get_img_by_id(
        self,
        img_id: str,
    ) -> bytes | None:
        """Fetch an image by its ID."""
        try:
            img: list[LanceSchema] = (
                self.db_table.search()
                .where(f"img_id == '{img_id}'")
                .limit(1)
                .to_pydantic(LanceSchema)
            )
            if not img:
                self.logger.warning(f"No image found with ID '{img_id}'.")
                return None
            return img[0].img_bytes

        except Exception as e:
            self.logger.error(f"Error fetching image with ID '{img_id}': {e}")
            return None

    def fetch_image(self, species_name: str) -> io.BytesIO | None:
        """Fetch a high-resolution image for a specific species.

        How it works:
        1. Query the database for images matching the species name.
        2. Compute the centroid of the embeddings.
        3. Select the image closest to the centroid.
        4. If not found, return None.
        :param species_name: The name of the species to fetch the image for.
        :return: The image bytes in PNG format or None if not found."""
        query = self._query_image(species_name)
        if query is None:
            return None
        return query[0].image_bytes_png

    def fetch_similar_images_from_text(
        self,
        request: Request,
        text: str,
        limit: int = 50,
        max_distance: float | None = None,
    ) -> list[dict] | None:
        """Fetch images similar to the given text.
        We use CLIP embeddings for text similarity search.
        We then filter the results to ensure it contains only one image per species.

        :param text: The input text to search for similar images.
        :param limit: The maximum number of similar images to return.
        :param max_distance: Optional maximum cosine distance threshold (0-2, lower is more similar).
                            For color searches, a more lenient threshold (e.g., 1.5) can help.
        :return: A list of dictionaries containing similar image details or None if no matches found.
        """
        try:
            text_embedder = ClipEmbedder(
                model=request.app.state.clip_embedder.model,
                processor=request.app.state.clip_embedder.processor,
            )
            query_embedding = text_embedder.get_embedding_from_text(text)
            if query_embedding is None:
                self.logger.warning("Failed to compute text embedding.")
                return None

            similar_images = self._query_embedding(
                query_vector=query_embedding,
                vector_column_name="clip_embeddings",
                limit=limit,
                max_distance=max_distance,
            )
            if similar_images is None or similar_images.is_empty():
                self.logger.warning("No similar images found for the given text.")
                return None
            self.logger.info(
                f"Found {len(similar_images)} similar images for the text '{text}'."
            )
            merged_results = self._merge_result_with_metadata(similar_images)
            if merged_results is None:
                return None
            similar_images = self._filter_by_species(merged_results)

            return similar_images.to_dicts()

        except Exception as e:
            self.logger.error(f"Error fetching similar images: {e}")
            return None

    def fetch_similar_images_from_text_filtered(
        self,
        request: Request,
        text: str,
        limit: int,
        filter_img_ids: List[str],
    ) -> List[dict]:
        """
        CLIP text search restricted to a specific set of image IDs.

        Mirrors fetch_similar_images_from_text but pre-filters the vector search
        to only images belonging to allowlisted species (from location/trait filters).

        Args:
            request: FastAPI request with CLIP model in app state
            text: Natural language color/pattern description
            limit: Maximum number of results to return
            filter_img_ids: Image IDs to restrict search to (from allowlist species)

        Returns:
            List of dicts with keys [imgId, species, distance] or [] on failure
        """
        if not filter_img_ids:
            logger.warning(
                "fetch_similar_images_from_text_filtered called with empty filter_img_ids"
            )
            return []

        try:
            # Step 1: Compute CLIP text embedding
            text_embedder = ClipEmbedder(
                model=request.app.state.clip_embedder.model,
                processor=request.app.state.clip_embedder.processor,
            )
            query_embedding = text_embedder.get_embedding_from_text(text)
            if query_embedding is None:
                self.logger.warning("Failed to compute text embedding.")
                return []

            # Step 2: Build SQL IN clause ? LanceDB WHERE uses SQL syntax
            # Wrap each ID in single quotes and join with commas
            ids_sql = ", ".join(f"'{img_id}'" for img_id in filter_img_ids)
            where_clause = f"img_id IN ({ids_sql})"

            # Step 3: Run vector search with pre-filter
            results = (
                self.db_table.search(
                    query_embedding,
                    vector_column_name="clip_embeddings",
                )
                .where(
                    where_clause, prefilter=True
                )  # prefilter=True scopes search to allowlist
                .distance_type("cosine")
                .limit(limit)
                .to_polars()
            )

            if results is None or results.is_empty():
                self.logger.warning(
                    f"No similar images found for text '{text}' within {len(filter_img_ids)} filtered IDs."
                )
                return []

            # Step 4: Select and rename columns to match pipeline schema
            safe_cols = [c for c in ("img_id", "_distance") if c in results.columns]
            if not safe_cols:
                return []

            cleaned = results.select(safe_cols).rename(
                {"img_id": "imgId", "_distance": "distance"}
            )

            # Step 5: Merge with metadata (adds species column)
            merged = self._merge_result_with_metadata(cleaned)
            if merged is None or merged.is_empty():
                return []

            # Step 6: Deduplicate by species, keep best (lowest) distance
            filtered = self._filter_by_species(merged)

            self.logger.info(
                f"Filtered color search: '{text}' ? {len(filtered)} species "
                f"within {len(filter_img_ids)} allowlisted images"
            )

            return filtered.to_dicts()

        except Exception as e:
            self.logger.error(
                f"Error in fetch_similar_images_from_text_filtered: {e}",
                exc_info=True,
            )
            return []

    def fetch_similar_images_from_bytes(
        self, request: Request, image_bytes: bytes, limit: int = 20
    ) -> list[dict] | None:
        """Fetch images similar to the given image bytes.
        We use UNICOM embeddings for image similarity search.
        We then filter the results to ensure it contains only one image per species.

        :param image_bytes: The input image bytes to search for similar images.
        :param limit: The maximum number of similar images to return.
        :return: A list of dictionaries containing similar image details or None if no matches found.
        """
        try:
            unicom_embedder = UnicomImageEmbedder(
                model=request.app.state.unicom_embedder.model,
                transform=request.app.state.unicom_embedder.transform,
            )
            query_embedding = unicom_embedder.get_embedding_from_bytes(image_bytes)
            if query_embedding is None:
                self.logger.warning("Failed to compute image embedding.")
                return None
            similar_images = self._query_embedding(
                query_vector=query_embedding,
                vector_column_name="unicom_embeddings",
                limit=limit,
            )
            if similar_images is None or similar_images.is_empty():
                self.logger.warning("No similar images found for the given image.")
                return None
            self.logger.info(
                f"Found {len(similar_images)} similar images for the provided image."
            )
            merged_results = self._merge_result_with_metadata(similar_images)
            if merged_results is None:
                return None
            filtered_imgs = self._filter_by_species(merged_results)
            return filtered_imgs.to_dicts()

        except Exception as e:
            self.logger.error(f"Error fetching similar images: {e}")
            return None

    def find_similar_images(
        self, image_ids: list[str], limit: int = 20
    ) -> pl.DataFrame | None:
        """Find images from other species similar to the given image list using UNICOM embeddings.

        Process:
          1. Fetch a representative image record for the species (currently only one via _query_image()).
          2. Use its UNICOM embedding (centroid if multiple in future).
          3. Run cosine similarity search against all stored unicom_embeddings.
          4. Keep at most one image per species (nearest match).
          5. Remove the original species from the results.

        Args:
            species_name: Species name (case/space insensitive).
            limit: Maximum number of similar (distinct) species to return (default 20).

        Returns:
            list of dicts with keys: imgId, species, distance (smaller = more similar),
            or None if no similar images were found.
        """
        query = self._query_images(image_ids)
        if query is None:
            return None
        # Compute the centroid of the embeddings
        centroid: np.ndarray = np.mean([img.unicom_embeddings for img in query], axis=0)
        # Perform similarity search based on the centroid
        try:
            results = self._query_embedding(
                query_vector=centroid,
                vector_column_name="unicom_embeddings",
                limit=limit,
            )
            self.logger.info(
                f"Found {len(results)} similar images for image IDs '{image_ids}'."
            )
            if results is None or results.is_empty():
                self.logger.warning(
                    f"No unique species found in similar images for image IDs '{image_ids}'."
                )
                return None
            merged_results = self._merge_result_with_metadata(results)
            # Filter to unique species and remove binary/embedding columns before JSON
            similar_images = self._filter_by_species(merged_results)
            return similar_images
        except Exception as e:
            self.logger.error(
                f"Error fetching similar images for image IDs '{image_ids}': {e}"
            )
            return None

    def fetch_thumbnail(self, species_name: str, limit: int = 5) -> io.BytesIO | None:
        """Fetch thumbnails for a specific species."""
        query = self._query_image(species_name)
        if query is None:
            return None
        return query[0].thumbnail_bytes_png

    def _query_embedding(
        self,
        query_vector: np.ndarray,
        vector_column_name: str,
        limit: int = 5,
        max_distance: float | None = None,
    ) -> pl.DataFrame | None:
        """Query the database for similar images based on the embedding vector.

        Args:
            query_vector: The embedding vector to search for
            vector_column_name: Name of the vector column to search
            limit: Maximum number of results to return
            max_distance: Optional maximum cosine distance threshold (0-2, lower is more similar).
                         If None, no distance filtering is applied.
        """
        try:
            results = (
                self.db_table.search(
                    query_vector,
                    vector_column_name=vector_column_name,
                )
                .distance_type("cosine")
                .limit(limit)
                .to_polars()
            )
            safe_cols = [c for c in ("img_id", "_distance") if c in results.columns]
            if not safe_cols:
                return None
            cleaned_results = results.select(safe_cols).rename(
                {"img_id": "imgId", "_distance": "distance"}
            )

            # Apply distance threshold if specified
            # For cosine distance: 0 = identical, 1 = orthogonal, 2 = opposite
            # Lower distance = more similar
            if max_distance is not None and "distance" in cleaned_results.columns:
                before_count = len(cleaned_results)
                cleaned_results = cleaned_results.filter(
                    pl.col("distance") <= max_distance
                )
                self.logger.info(
                    f"Distance filter ({max_distance}): {before_count} -> {len(cleaned_results)} results"
                )

            # We filter image by unique image IDs to avoid duplicates
            cleaned_results = cleaned_results.unique(subset=["imgId"])
            return cleaned_results
        except Exception as e:
            self.logger.error(f"Error querying embeddings: {e}")
            return None

    def _compute_distance(
        self, source_emb: np.ndarray, target_emb: np.ndarray
    ) -> float:
        """Compute the Euclidean distance between two embeddings."""
        return np.linalg.norm(source_emb - target_emb)

    def _query_images(self, image_ids: list[str]) -> list[LanceSchema] | None:
        """Construct a query string for fetching images."""
        image_data: list[LanceSchema] = []
        for img_id in image_ids:
            img_record = self._get_image_data_by_id(img_id)
            if img_record is not None:
                image_data.append(img_record)
        if not image_data:
            self.logger.warning("No images found for the provided image IDs.")
            return None
        return image_data

    def _get_image_data_by_id(self, img_id: str) -> LanceSchema | None:
        """Fetch an image record by its ID."""
        try:
            img: list[LanceSchema] = (
                self.db_table.search()
                .where(f"img_id == '{img_id}'")
                .limit(1)
                .to_pydantic(LanceSchema)
            )
            if not img:
                self.logger.warning(f"No image found with ID '{img_id}'.")
                return None
            return img[0]

        except Exception as e:
            self.logger.error(f"Error fetching image with ID '{img_id}': {e}")
            return None

    def _merge_result_with_metadata(
        self,
        results: pl.DataFrame,
    ) -> pl.DataFrame | None:
        """
        Query the DuckDB for metadata and merge with the results.
        :param results: The polars DataFrame containing search results.
        """
        try:
            if results is None:
                self.logger.warning("No results to merge with metadata.")
                return results

            meta_service = ImageMetaService(duckdb=self.meta_table)
            merged_results = meta_service.merge_meta_with_image_data(results)

            return merged_results

        except Exception as e:
            self.logger.error(f"Error merging results with metadata: {e}")
            return results

    def _filter_by_species(self, results: pl.DataFrame) -> pl.DataFrame:
        """Filter the results to ensure only one image per species is kept."""
        try:
            if results is None:
                self.logger.warning("No results to filter by species.")
                return results

            # Keep the first occurrence of each species
            filtered_results = (
                results.sort("distance")
                .unique(subset=["species"], maintain_order=True)
                .sort("distance", descending=True)
            )

            return filtered_results

        except Exception as e:
            self.logger.error(f"Error filtering results by species: {e}")
            return results
