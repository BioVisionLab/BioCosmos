import glob
import numpy as np
import io
import logging
import os
import concurrent.futures
import polars as pl
from tqdm import tqdm

from PIL.Image import Image as PILImage
from PIL import Image

from ..configs.config import EmbedderConfig, ImageConfig
from ..database.lance import LanceDB
from .unicom import UnicomImageEmbedder
from .clip import ClipEmbedder



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
        self.img_format = self.config.format.upper()
        self.max_resolution = self.config.max_resolution
        self.clip = ClipEmbedder(
            model=clip_model,
            processor=clip_processor,
        )
        self.unicom = UnicomImageEmbedder(
            model=unicom_model,
            transform=unicom_transform,
        )
        self.logger = logging.getLogger(__name__)
        self.db_table = lance_db.create_or_get_collection(self.config.table)

    def ingest(self):
        """Ingest images into the database."""
        if self.embedder_config.skip:
            self.logger.info("Skipping image ingestion as per configuration.")
            return
        img_paths = self._get_images_from_path(self.config.dir)
        if not img_paths:
            self.logger.error("No image paths provided for ingestion.")
            return
        if not self.embedder_config.reset:
            entries = LanceDB().count_entries(self.config.table)
            if entries == len(img_paths):
                self.logger.info(
                    "Image entries already exist in the database. Skipping ingestion."
                )
                return
        if self.config.limit is not None:
            self.logger.info(f"Limiting image ingestion to {self.config.limit} images.")
            self.batch_add_embeddings(self._limit_entries(img_paths))
        else:
            self.batch_add_embeddings(img_paths)
        self.logger.info("Image ingestion completed.")

    def get_species_name_from_path(self, img_paths: list[str]) -> list[str]:
        return [os.path.basename(os.path.dirname(path)) for path in img_paths]

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
                executor.submit(self._add_batch_to_db, batch) for batch in batches
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

    def _limit_entries(self, img_paths: list[str]) -> list[str]:
        """Limit the number of image paths based on configuration.
        Determines the img paths based on the file extension for quick filtering.
        Later stages will validate the actual image files and skip invalid ones.
        """
        if (
            self.config.limit is not None
            and self.config.limit > 0
            and len(img_paths) > self.config.limit
        ):
            self.logger.info(f"Limiting image ingestion to {self.config.limit} images.")
            return img_paths[: self.config.limit]
        return img_paths

    def _get_images_from_path(self, img_dir: str) -> list[str]:
        """Get a list of image paths from the specified directory."""
        if not os.path.isdir(img_dir):
            self.logger.error(f"Invalid image directory: {img_dir}")
            return []
        pattern = os.path.join(img_dir, "**") + "/*"
        img_paths = [
            f for f in glob.glob(pattern, recursive=True) if self._valid_img_path(f)
        ]
        self.logger.info(f"Found {len(img_paths)} images in {img_dir}.")
        return img_paths

    def _valid_img_path(self, img_path: str) -> bool:
        """Check if the image path is valid and points to an image file."""
        valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
        return os.path.isfile(img_path) and img_path.lower().endswith(valid_extensions)

    def _add_batch_to_db(self, img_paths: list[str]):
        """Batch add image embeddings to the database."""
        if not img_paths:
            self.logger.error("No image paths provided for batch addition.")
            return

        successful_paths, valid_images = self._get_imgs(img_paths)
        if not valid_images:
            self.logger.error("No valid images found for batch addition.")
            return
        try:
            clip_embeddings: list[np.ndarray] = self._get_all_clip_embeddings(
                valid_images
            )
            unicom_embeddings: list[np.ndarray] = self._get_all_unicom_embeddings(
                valid_images
            )

            if any(e is None for e in clip_embeddings):
                self.logger.error(
                    "Some embeddings could not be computed. Skipping batch addition."
                )
                return
        except Exception as e:
            self.logger.error(
                f"Error computing embeddings for batch: {e}",
                exc_info=True,
            )
            return
        # Now process image bytes (preserving transparency from original images)
        image_bytes, original_size_flags = self._get_image_bytes(valid_images)

        if not image_bytes:
            self.logger.error("No valid image bytes found for batch addition.")
            return

        data = pl.DataFrame(
            {
                "img_id": self._get_image_ids_from_paths(successful_paths),
                "img_bytes": image_bytes,
                "file_format": self.config.format,
                "original_size": original_size_flags,
                "clip_embeddings": clip_embeddings,
                "unicom_embeddings": unicom_embeddings,
            }
        )
        self._insert_batch_to_db(data)

    def _insert_batch_to_db(self, data: pl.DataFrame):
        """Insert a batch of data into the database."""
        try:
            arrow_table = data.to_arrow().cast(self.db_table.schema)
            self.db_table.merge_insert("img_id").when_not_matched_insert_all().execute(
                arrow_table
            )
        except Exception as e:
            self.logger.error(
                f"Error inserting batch to database: {e}",
                exc_info=True,
            )

    def _img_exists_in_db(self, img_id: str) -> bool:
        """Check if an image ID exists in the database."""
        try:
            exists = (
                self.db_table.search()
                .where(f"img_id == '{img_id}'")
                .limit(1)
                .to_polars()
                .is_empty()
                is False
            )
            return exists
        except Exception as e:
            self.logger.error(f"Error checking existence of image ID '{img_id}': {e}")
            return False

    def _get_image_ids_from_paths(self, img_paths: list[str]) -> list[str]:
        """Get image IDs from a list of image paths."""
        return [self._get_image_id(path) for path in img_paths]

    def _get_image_id(self, img_path: str) -> str:
        """Get image ID from an image path."""
        return os.path.splitext(os.path.basename(img_path))[0]

    def _get_image_bytes(
        self, images: list[PILImage]
    ) -> tuple[list[bytes], list[bool]]:
        """Get the image bytes from a list of PIL Images.
        It will resize the image if setup in the config to a maximum resolution.
        Returns image bytes for successfully processed images and a flag indicating
        if all images are of original size.
        """
        valid_image_bytes = []
        all_original_size = []
        for img in images:
            try:
                img_byte_arr = io.BytesIO()
                if max(img.size) > self.max_resolution:
                    img.thumbnail(
                        (self.max_resolution, self.max_resolution),
                        resample=Image.LANCZOS,
                    )
                    all_original_size.append(False)
                else:
                    all_original_size.append(True)
                img.save(img_byte_arr, format=self.img_format)
                valid_image_bytes.append(img_byte_arr.getvalue())
                img.close()
            except Exception as e:
                self.logger.error(
                    f"Error converting image to bytes: {e}",
                    exc_info=True,
                )
        return valid_image_bytes, all_original_size

    def _get_imgs(self, img_paths: list[str]) -> tuple[list[str], list[PILImage]]:
        """Get the image embeddings from a list of image paths.
        Returns a tuple of successfully processed image paths and the image files.
        """
        valid_images = []
        successful_paths = []
        for img_path in img_paths:
            try:
                img = Image.open(img_path)
                # Load image to memory to avoid file handle issues
                img.load()
                # Don't convert to RGB here - do it only when needed for embeddings
                valid_images.append(img)
                successful_paths.append(img_path)
            except FileNotFoundError:
                self.logger.warning(f"Image file not found, skipping: {img_path}")
            except Exception as e:
                self.logger.error(
                    f"Error opening image {img_path}: {e}",
                    exc_info=True,
                )
        return successful_paths, valid_images

    def _split_batch(self, img_paths: list[str]):
        """Split the list of image paths into smaller batches."""
        if not img_paths:
            self.logger.error("No image paths provided for splitting.")
            return []
        batches = [
            img_paths[i : i + self.embedder_config.batch_size]
            for i in range(0, len(img_paths), self.embedder_config.batch_size)
        ]
        self.logger.info(
            f"Split {len(img_paths)} image paths into {len(batches)} batches."
        )
        return batches

    def _get_all_clip_embeddings(self, img_paths: list[str]) -> list[np.ndarray]:
        return self.clip.batch_get_embeddings(img_paths)

    def _get_all_unicom_embeddings(self, img_paths: list[str]) -> list[np.ndarray]:
        return self.unicom.batch_get_embeddings(img_paths)
