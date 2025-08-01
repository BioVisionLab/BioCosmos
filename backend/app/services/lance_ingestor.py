import numpy as np

# We experiment with polars for better performance instead of pandas
from .services.unicom import UnicomImageEmbedder
import polars as pl
from tqdm import tqdm
from .clip import ClipEmbedder
import logging
import os

logger = logging.getLogger(__name__)


class LanceDbIngestor:
    """Class to handle database operations for CLIP embeddings."""

    def __init__(self, table):
        self.clip = ClipEmbedder()
        self.unicom = UnicomImageEmbedder()
        self.logger = logger
        self.table = table

    def get_species_name_from_path(
        self, img_paths: list[str]
    ) -> list[str]:
        return [
            os.path.basename(os.path.dirname(path))
            for path in img_paths
        ]

    def batch_add_embeddings(self, img_paths: list[str]):
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
        intern_embeddings: list[np.ndarray] = (
            self.get_all_intern_embeddings(img_paths)
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
                "intern_embeddings": intern_embeddings,
            }
        )
        try:
            self.table.add(data)
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
        # We track progress using tqdm
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

    def get_all_intern_embeddings(self, img_paths: list[str]):
        embeddings: list[np.ndarray] = []
        # We track progress using tqdm
        for img_path in tqdm(
            img_paths, desc="Computing Intern-VL embeddings"
        ):
            embedding = self.intern_vl.get_embedding_from_path(
                img_path
            )
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
