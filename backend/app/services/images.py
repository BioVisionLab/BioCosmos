import glob
import numpy as np
import io

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

IMG_DIR = "../../../python/biocosmos-exploration/data/images"
COLLECTION_NAME = "biocosmos_images"


class ImagePersistData:
    """Class to handle image persistence operations."""

    def __init__(self):
        self.logger = logger
        self.db_table = LanceDB().create_or_get_collection(
            COLLECTION_NAME
        )

    def entries(self) -> int | None:
        """Count the number of entries in the image collection."""
        result = LanceDB().count_entries(COLLECTION_NAME)
        if result is None:
            logger.warning(
                "No entries found in the image collection."
            )
            return None
        return result

    def fetch_thumbnail(
        self, species_name: str, limit: int = 5
    ) -> io.BytesIO | None:
        """Fetch thumbnails for a specific species."""
        species = species_name.lower().replace(" ", "_")
        query = f"species == '{species}'"
        try:
            img: list[LanceSchema] = (
                self.db_table.search()
                .where(query)
                .limit(limit)
                .to_pydantic(LanceSchema)
            )
            if not img:
                self.logger.warning(
                    f"No images found for species '{species_name}'."
                )
                return None
            thumbnails = [img.thumbnail_bytes_png for img in img]
            return thumbnails[0] if thumbnails else None
        except Exception as e:
            self.logger.error(
                f"Error fetching images for species '{species_name}': {e}"
            )
        finally:
            self.logger.info(
                f"Finished fetching images for species: {species_name}"
            )

    def ingest(self, img_dir: str = IMG_DIR):
        """Ingest images into the database."""
        img_paths = self.get_images_from_path(img_dir)
        if not img_paths:
            self.logger.error(
                "No image paths provided for ingestion."
            )
            return
        self.logger.info(f"Ingesting {len(img_paths)} images.")
        ImageEmbedder().batch_add_embeddings(img_paths)

    def get_images_from_path(self, img_dir: str) -> list[str]:
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


class ImageEmbedder(ImagePersistData):
    """Class to handle image embedding operations.
    Include methods for adding, updating, and deleting image data, metadata, and embeddings.
    """

    def __init__(self):
        self.clip = ClipEmbedder()
        self.unicom = UnicomImageEmbedder()
        super().__init__()

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
                "source": "gbif",
                "collection_id": "gbif",
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
