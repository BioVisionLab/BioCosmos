import glob
import numpy as np
import io

from pydantic import BaseModel

from ..configs.config import ImageConfig
from ..database.model import LanceSchema
from ..database.lance import LanceDB

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


# class SimilarImageResult(BaseModel):
#     """Class to represent similar image search results."""

#     img_id: str
#     species: str
#     distance: float

#     def to_dict(self) -> dict:
#         return {
#             "imgId": self.img_id,
#             "species": self.species,
#             "distance": self.distance,
#         }


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

    def __init__(self):
        self.config = ImageConfig()
        self.logger = logging.getLogger(__name__)
        self.db_table = LanceDB().create_or_get_collection(
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
            results = self.db_table.search().where(query).to_polars()
            if "img_id" not in results.columns or results.is_empty():
                self.logger.warning(
                    f"No image IDs found for species '{species_name}'."
                )
                return []

            return SpeciesImage(
                species=species,
                imageIds=results["img_id"].to_list(),
            ).to_dict()
        except Exception as e:
            self.logger.error(
                f"Error fetching image IDs for species '{species_name}': {e}"
            )
            return []

    def get_img_by_id(
        self, img_id: str, is_thumbnail: bool = False
    ) -> io.BytesIO | None:
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
            return (
                img[0].thumbnail_bytes_png
                if is_thumbnail
                else img[0].image_bytes_png
            )
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
        self, text: str, limit: int = 50
    ) -> list[dict] | None:
        """Fetch images similar to the given text.
        We use CLIP embeddings for text similarity search.
        We then filter the results to ensure it contains only one image per species.

        :param text: The input text to search for similar images.
        :param limit: The maximum number of similar images to return.
        :return: A list of dictionaries containing similar image details or None if no matches found.
        """
        try:
            text_embedder = ClipEmbedder()
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
            similar_images = self._filter_by_species(
                similar_images, limit=limit
            )
            return similar_images.to_dicts()

        except Exception as e:
            self.logger.error(f"Error fetching similar images: {e}")
            return None

    def fetch_similar_images_from_bytes(
        self, image_bytes: bytes, limit: int = 20
    ) -> list[dict] | None:
        """Fetch images similar to the given image bytes.
        We use UNICOM embeddings for image similarity search.
        We then filter the results to ensure it contains only one image per species.

        :param image_bytes: The input image bytes to search for similar images.
        :param limit: The maximum number of similar images to return.
        :return: A list of dictionaries containing similar image details or None if no matches found.
        """
        try:
            unicom_embedder = UnicomImageEmbedder()
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
            # return polars DataFrame as list of dicts
            return similar_images.write_json()

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
        # We get unicom embeddings for similarity search
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
            if similar_images is None or similar_images.is_empty():
                self.logger.warning(
                    f"No unique species found in similar images for '{species_name}'."
                )
                return None
            filtered_imgs = self._filter_by_species(
                similar_images, limit=limit
            )

            filtered_imgs = filtered_imgs.filter(
                pl.col("species")
                != species_name.lower().replace(" ", "_")
            ).sort("species")
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
            return cleaned_results
        except Exception as e:
            self.logger.error(f"Error querying embeddings: {e}")
            return None

    def _filter_by_species(
        self, df: pl.DataFrame, limit: int = 5
    ) -> pl.DataFrame:
        """Filter the DataFrame to ensure only one image per species.
        We sort by distance and keep the first occurrence of each species.
        """
        if df is None or df.is_empty():
            return df
        # Sort by distance
        df = df.sort("distance")
        # Keep only the first occurrence of each species
        filtered_df = df.unique(subset=["species"])
        if len(filtered_df) > limit:
            filtered_df = filtered_df.head(limit)
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
                .limit(1)
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

    def __init__(self):
        self.config = ImageConfig()
        self.clip = ClipEmbedder()
        self.unicom = UnicomImageEmbedder()
        self.logger = logging.getLogger(__name__)
        self.db_table = LanceDB().create_or_get_collection(
            self.config.table
        )

    def ingest(self):
        """Ingest images into the database."""

        img_paths = self._get_images_from_path(self.config.dir)
        if not img_paths:
            self.logger.error(
                "No image paths provided for ingestion."
            )
            return
        if not self.config.reset:
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
        batches = self.split_batch(img_paths)
        if not batches:
            self.logger.error("No batches to process.")
            return

        self.logger.info(
            f"Starting concurrent batch addition of {len(img_paths)} images."
        )
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self._add_batch_to_db, batch)
                for batch in batches
            ]
            for future in concurrent.futures.as_completed(futures):
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
        species = self.get_species_name_from_path(img_paths)
        image_bytes = [open(path, "rb").read() for path in img_paths]
        clip_embeddings: list[np.ndarray] = (
            self.get_all_clip_embeddings(img_paths)
        )
        unicom_embeddings: list[np.ndarray] = (
            self.get_all_unicom_embeddings(img_paths)
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
                    for path in img_paths
                ],
                "species": species,
                "img_bytes": image_bytes,
                "clip_embeddings": clip_embeddings,
                "unicom_embeddings": unicom_embeddings,
            }
        )
        try:
            self.db_table.add(data)
            self.logger.info(
                f"Batch added {len(img_paths)} embeddings to the database."
            )
        except Exception as e:
            self.logger.error(
                f"Error adding batch embeddings: {e}", exc_info=True
            )
            return

    def split_batch(
        self, img_paths: list[str], batch_size: int = 100
    ):
        """Split the list of image paths into smaller batches."""
        if not img_paths:
            self.logger.error(
                "No image paths provided for splitting."
            )
            return []
        batches = [
            img_paths[i : i + batch_size]
            for i in range(0, len(img_paths), batch_size)
        ]
        self.logger.info(
            f"Split {len(img_paths)} image paths into {len(batches)} batches."
        )
        return batches

    def get_all_clip_embeddings(self, img_paths: list[str]):
        embeddings: list[np.ndarray] = []
        for img_path in tqdm(
            img_paths, desc="Computing CLIP embeddings"
        ):
            embedding = self.clip.get_embedding_from_img(img_path)
            if embedding is not None:
                embeddings.append(embedding)
            else:
                self.logger.error(
                    f"Failed to compute embedding for {img_path}"
                )
        # Fix: Use explicit check for None in list of arrays
        if any(e is None for e in embeddings):
            self.logger.error(
                "Some embeddings could not be computed. Skipping batch addition."
            )
            return
        return embeddings

    def get_all_unicom_embeddings(self, img_paths: list[str]):
        embeddings: list[np.ndarray] = []
        for img_path in tqdm(
            img_paths, desc="Computing Unicom embeddings"
        ):
            embedding = self.unicom.get_embedding_from_img(img_path)
            if embedding is not None:
                embeddings.append(embedding)
            else:
                self.logger.error(
                    f"Failed to compute embedding for {img_path}"
                )
        # Fix: Use explicit check for None in list of arrays
        if any(e is None for e in embeddings):
            self.logger.error(
                "Some embeddings could not be computed. Skipping batch addition."
            )
            return
        return embeddings
