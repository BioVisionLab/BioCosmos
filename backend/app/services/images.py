import glob
import numpy as np
import io

from PIL import Image
from pydantic import BaseModel

from ..configs.config import EmbedderConfig, ImageConfig
from ..database.model import LanceSchema
from ..database.lance import LanceDB
from fastapi import Request

# We experiment with polars for better performance instead of pandas
from .unicom import UnicomImageEmbedder
import polars as pl
from tqdm import tqdm
from .clip import ClipEmbedder
import logging
import os
import concurrent.futures

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


class ImageSummary:
    """Class to represent image summary data."""

    def __init__(self, lance_db: LanceDB):
        self.logger = logging.getLogger(__name__)
        self.config = ImageConfig()
        self.db_table = lance_db.create_or_get_collection(
            self.config.table
        )

    def get_count(self, species_name: str) -> int | None:
        """Fetch image statistics for a specific species.

        How it works:
        1. Query the database for images matching the species name.
        2. Return statistics such as number of images available.
        :param species_name: The name of the species to fetch the image statistics for.
        :return: A dictionary containing image statistics or None if not found."""
        query = self._query_image(species_name)

        return len(query) if query is not None else None

    def _query_image(self, species_name: str) -> pl.DataFrame | None:
        """Construct a query string for fetching images."""
        species = species_name.lower().replace(" ", "_")
        query = f"species == '{species}'"
        try:
            results = self.db_table.search().where(query).to_polars()
            if results.is_empty():
                self.logger.warning(
                    f"No images found for species '{species_name}'."
                )
                return None

            dedup_images = results.unique(subset=["img_id"])
            return dedup_images
        except Exception as e:
            self.logger.error(
                f"Error fetching images for species '{species_name}': {e}"
            )
            return None


class ImagePersistData:
    """Class to handle image persistence operations."""

    def __init__(self, lance_db: LanceDB):
        self.config = ImageConfig()
        self.logger = logging.getLogger(__name__)
        self.db_table = lance_db.create_or_get_collection(
            self.config.table
        )

    def entries(self) -> int | None:
        """Count the number of entries in the image collection."""
        result = LanceDB().count_entries(self.config.table)
        if result is None:
            logger.warning(
                "No entries found in the image collection."
            )
            return None
        return result

    # Function to fetch a list of image IDs for a given species
    # Returns species name and list of image IDs, or empty list if none found
    def fetch_image_ids(self, species_name: str) -> list:
        """
        Returns a list of image IDs for the given species name.
        """
        species = species_name.lower().replace(" ", "_")
        query = f"species == '{species}'"
        try:
            results = (
                self.db_table.search()
                .where(query)
                .limit(10)
                .to_polars()
            )
            if "img_id" not in results.columns or results.is_empty():
                self.logger.warning(
                    f"No image IDs found for species '{species_name}'."
                )
                return []
            # Result may contain duplicates image IDs, so we deduplicate
            dedup_results = results.unique(subset=["img_id"])
            return SpeciesImage(
                species=species,
                imageIds=dedup_results["img_id"].to_list(),
            ).to_dict()
        except Exception as e:
            self.logger.error(
                f"Error fetching image IDs for species '{species_name}': {e}"
            )
            return []

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
                self.logger.warning(
                    f"No image found with ID '{img_id}'."
                )
                return None
            return img[0].img_bytes

        except Exception as e:
            self.logger.error(
                f"Error fetching image with ID '{img_id}': {e}"
            )
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
        self, request: Request, text: str, limit: int = 50
    ) -> list[dict] | None:
        """Fetch images similar to the given text.
        We use CLIP embeddings for text similarity search.
        We then filter the results to ensure it contains only one image per species.

        :param text: The input text to search for similar images.
        :param limit: The maximum number of similar images to return.
        :return: A list of dictionaries containing similar image details or None if no matches found.
        """
        try:
            text_embedder = ClipEmbedder(
                model=request.app.state.clip_embedder.model,
                processor=request.app.state.clip_embedder.processor,
            )
            query_embedding = text_embedder.get_embedding_from_text(
                text
            )
            if query_embedding is None:
                self.logger.warning(
                    "Failed to compute text embedding."
                )
                return None

            similar_images = self._query_embedding(
                query_vector=query_embedding,
                vector_column_name="clip_embeddings",
                limit=limit,
            )
            if similar_images is None or similar_images.is_empty():
                self.logger.warning(
                    "No similar images found for the given text."
                )
                return None
            self.logger.info(
                f"Found {len(similar_images)} similar images for the text '{text}'."
            )
            # Filter to unique species and remove binary/embedding columns before JSON
            similar_images = self._filter_by_species(similar_images)

            return similar_images.to_dicts()

        except Exception as e:
            self.logger.error(f"Error fetching similar images: {e}")
            return None

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
            query_embedding = (
                unicom_embedder.get_embedding_from_bytes(image_bytes)
            )
            if query_embedding is None:
                self.logger.warning(
                    "Failed to compute image embedding."
                )
                return None
            similar_images = self._query_embedding(
                query_vector=query_embedding,
                vector_column_name="unicom_embeddings",
                limit=limit,
            )
            if similar_images is None or similar_images.is_empty():
                self.logger.warning(
                    "No similar images found for the given image."
                )
                return None
            self.logger.info(
                f"Found {len(similar_images)} similar images for the provided image."
            )
            return similar_images.to_dicts()

        except Exception as e:
            self.logger.error(f"Error fetching similar images: {e}")
            return None

    def fetch_id_similar_images(
        self, species_name: str, limit: int = 20
    ) -> list[dict] | None:
        """Find images from other species similar to the given species using UNICOM embeddings.

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
        self.logger.info(
            f"Fetching images similar to species '{species_name}'"
        )
        query = self._query_image(species_name)
        if query is None:
            return None
        # Compute the centroid of the embeddings
        centroid: np.ndarray = np.mean(
            [img.unicom_embeddings for img in query], axis=0
        )
        # Perform similarity search based on the centroid
        try:
            similar_images = self._query_embedding(
                query_vector=centroid,
                vector_column_name="unicom_embeddings",
                limit=limit,
            )
            self.logger.info(
                f"Found {len(similar_images)} similar images for species '{species_name}'."
            )
            if similar_images is None or similar_images.is_empty():
                self.logger.warning(
                    f"No unique species found in similar images for '{species_name}'."
                )
                return None
            filtered_imgs = self._filter_by_species(similar_images)

            filtered_imgs = filtered_imgs.filter(
                pl.col("species")
                != species_name.lower().replace(" ", "_")
            ).sort("species")
            self.logger.info(
                f"Found {len(filtered_imgs)} similar images after filtering."
            )
            return filtered_imgs.to_dicts()
        except Exception as e:
            self.logger.error(
                f"Error fetching similar images for species '{species_name}': {e}"
            )
            return None

    def fetch_thumbnail(
        self, species_name: str, limit: int = 5
    ) -> io.BytesIO | None:
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
    ) -> pl.DataFrame | None:
        """Query the database for similar images based on the embedding vector."""
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
            safe_cols = [
                c
                for c in ("img_id", "species", "_distance")
                if c in results.columns
            ]
            if not safe_cols:
                return None
            cleaned_results = results.select(safe_cols).rename(
                {"img_id": "imgId", "_distance": "distance"}
            )
            # We filter image by unique image IDs to avoid duplicates
            cleaned_results = cleaned_results.unique(subset=["imgId"])
            return cleaned_results
        except Exception as e:
            self.logger.error(f"Error querying embeddings: {e}")
            return None

    def _filter_by_species(self, df: pl.DataFrame) -> pl.DataFrame:
        """Filter the DataFrame to ensure only one image per species.
        We sort by distance and keep the first occurrence of each species.
        """
        if df is None or df.is_empty():
            return df
        # Sort by distance
        df = df.sort("distance")
        # Keep only the first occurrence of each species
        filtered_df = df.unique(subset=["species"])
        self.logger.info(
            f"Filtered to {len(df)} of {len(filtered_df)} species."
        )
        return filtered_df

    def _compute_distance(
        self, source_emb: np.ndarray, target_emb: np.ndarray
    ) -> float:
        """Compute the Euclidean distance between two embeddings."""
        return np.linalg.norm(source_emb - target_emb)

    def _query_image(
        self, species_name: str
    ) -> list[LanceSchema] | None:
        """Construct a query string for fetching images."""
        species = species_name.lower().replace(" ", "_")
        query = f"species == '{species}'"
        try:
            img: list[LanceSchema] = (
                self.db_table.search()
                .where(query)
                .to_pydantic(LanceSchema)
            )
            if not img:
                self.logger.warning(
                    f"No images found for species '{species_name}'."
                )
                return None
            return img
        except Exception as e:
            self.logger.error(
                f"Error fetching images for species '{species_name}': {e}"
            )


class ImageEmbedder:
    """Class to handle image embedding operations.
    Include methods for adding, updating, and deleting image data, metadata, and embeddings.
    """

    def __init__(
        self,
        clip_model,
        clip_processor,
        unicom_model,
        unicom_transform,
        lance_db: LanceDB,
    ):
        self.embedder_config = EmbedderConfig()
        self.config = ImageConfig()
        self.clip = ClipEmbedder(
            model=clip_model,
            processor=clip_processor,
        )
        self.unicom = UnicomImageEmbedder(
            model=unicom_model,
            transform=unicom_transform,
        )
        self.logger = logging.getLogger(__name__)
        self.db_table = lance_db.create_or_get_collection(
            self.config.table
        )

    def ingest(self):
        """Ingest images into the database."""
        if self.embedder_config.skip:
            self.logger.info(
                "Skipping image ingestion as per configuration."
            )
            return
        img_paths = self._get_images_from_path(self.config.dir)
        if not img_paths:
            self.logger.error(
                "No image paths provided for ingestion."
            )
            return
        if not self.embedder_config.reset:
            entries = LanceDB().count_entries(self.config.table)
            if entries == len(img_paths):
                self.logger.info(
                    "Image entries already exist in the database. Skipping ingestion."
                )
                return

        self.logger.info(f"Ingesting {len(img_paths)} images.")
        self.batch_add_embeddings(img_paths)

    def get_species_name_from_path(
        self, img_paths: list[str]
    ) -> list[str]:
        return [
            os.path.basename(os.path.dirname(path))
            for path in img_paths
        ]

    def batch_add_embeddings(self, img_paths: list[str]):
        batches = self._split_batch(img_paths)
        if not batches:
            self.logger.error("No batches to process.")
            return

        self.logger.info(
            f"Starting concurrent batch addition of {len(img_paths)} images."
        )
        # Suppress excessive logging from watchfiles during concurrent processing
        logging.getLogger("watchfiles").setLevel(logging.WARNING)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self._add_batch_to_db, batch)
                for batch in batches
            ]

            progress_bar = tqdm(
                concurrent.futures.as_completed(futures),
                total=len(batches),
                desc="Processing batches",
            )

            for future in progress_bar:
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(
                        f"Error in concurrent batch addition: {e}",
                        exc_info=True,
                    )

    def _get_images_from_path(self, img_dir: str) -> list[str]:
        """Get a list of image paths from the specified directory."""
        if not os.path.isdir(img_dir):
            self.logger.error(f"Invalid image directory: {img_dir}")
            return []
        pattern = os.path.join(img_dir, "**") + "/*"
        img_paths = [
            f
            for f in glob.glob(pattern, recursive=True)
            if f.lower().endswith(
                (".png", ".jpg", ".jpeg", ".webp", ".bmp")
            )
            and os.path.isfile(f)
        ]
        self.logger.info(
            f"Found {len(img_paths)} images in {img_dir}."
        )
        return img_paths

    def _add_batch_to_db(self, img_paths: list[str]):
        """Batch add image embeddings to the database."""
        if img_paths is None or len(img_paths) == 0:
            self.logger.error(
                "No image paths provided for batch addition."
            )
            return
        successful_paths, valid_images = self._get_imgs(img_paths)
        if not valid_images or len(valid_images) == 0:
            self.logger.error(
                "No valid images found for batch addition."
            )
            return
        image_bytes = [
            open(path, "rb").read() for path in successful_paths
        ]
        species = self.get_species_name_from_path(successful_paths)
        clip_embeddings: list[np.ndarray] = (
            self._get_all_clip_embeddings(valid_images)
        )
        unicom_embeddings: list[np.ndarray] = (
            self._get_all_unicom_embeddings(valid_images)
        )
        # Fix: Use explicit check for None in list of arrays
        if any(e is None for e in clip_embeddings):
            self.logger.error(
                "Some embeddings could not be computed. Skipping batch addition."
            )
            return
        data = pl.DataFrame(
            {
                "img_id": [
                    os.path.splitext(os.path.basename(path))[0]
                    for path in successful_paths
                ],
                "species": species,
                "img_bytes": image_bytes,
                "clip_embeddings": clip_embeddings,
                "unicom_embeddings": unicom_embeddings,
            }
        )
        try:
            self.db_table.add(data)
        except Exception as e:
            self.logger.error(
                f"Error adding batch embeddings: {e}", exc_info=True
            )
            return

    def _get_imgs(
        self, img_paths: list[str]
    ) -> tuple[list[str], list[Image]]:
        """Get the image embeddings from a list of image paths.
        Returns a tuple of successfully processed image paths and their embeddings.
        """
        valid_images = []
        successful_paths = []
        for img_path in img_paths:
            try:
                img: Image = Image.open(img_path).convert("RGB")
                valid_images.append(img)
                successful_paths.append(img_path)
            except FileNotFoundError:
                self.logger.warning(
                    f"Image file not found, skipping: {img_path}"
                )
            except Exception as e:
                self.logger.error(
                    f"Error opening image {img_path}: {e}",
                    exc_info=True,
                )
        return successful_paths, valid_images

    def _split_batch(self, img_paths: list[str]):
        """Split the list of image paths into smaller batches."""
        if not img_paths:
            self.logger.error(
                "No image paths provided for splitting."
            )
            return []
        batches = [
            img_paths[i : i + self.embedder_config.batch_size]
            for i in range(
                0, len(img_paths), self.embedder_config.batch_size
            )
        ]
        self.logger.info(
            f"Split {len(img_paths)} image paths into {len(batches)} batches."
        )
        return batches

    def _get_all_clip_embeddings(
        self, img_paths: list[str]
    ) -> list[np.ndarray]:
        return self.clip.batch_get_embeddings(img_paths)

    def _get_all_unicom_embeddings(
        self, img_paths: list[str]
    ) -> list[np.ndarray]:
        return self.unicom.batch_get_embeddings(img_paths)
