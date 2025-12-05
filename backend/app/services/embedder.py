import glob
import numpy as np
import io
import os
import logging
import concurrent.futures
import itertools
from typing import Generator, List, Tuple

import polars as pl
from PIL import Image

from tqdm import tqdm

from ..configs.config import EmbedderConfig, ImageConfig
from ..database.lance import LanceDB
from .unicom import UnicomImageEmbedder
from .clip import ClipEmbedder


class ImageEmbedder:
    """
    A class responsible for the end-to-end pipeline of image ingestion and embedding.

    This class manages:
    1.  **Scanning**: Efficiently finding images in a directory structure using generators.
    2.  **Processing**: Loading images, validating formats, resizing if necessary, and converting to bytes.
        It includes optimizations to bypass re-encoding if the source image already meets criteria.
    3.  **Embedding**: Generating semantic vector embeddings using CLIP and UniCOM models.
    4.  **Storage**: Storing metadata, raw image bytes, and embeddings into a LanceDB table.

    Attributes:
        embedder_config (EmbedderConfig): Configuration for embedding parameters (batch size, device, etc.).
        config (ImageConfig): Configuration for image specifications (directory, format, resolution, table name).
        clip (ClipEmbedder): Wrapper for the CLIP model.
        unicom (UnicomImageEmbedder): Wrapper for the UniCOM model.
        db_table (LanceDB.table): The database table connection.
    """

    def __init__(
        self,
        clip_model,
        clip_processor,
        unicom_model,
        unicom_transform,
        lance_db: LanceDB,
    ):
        """
        Initialize the ImageEmbedder with model components and database connection.

        Args:
            clip_model: The pre-loaded CLIP model instance.
            clip_processor: The pre-loaded CLIP processor/transform.
            unicom_model: The pre-loaded UniCOM model instance.
            unicom_transform: The pre-loaded UniCOM transform function.
            lance_db (LanceDB): The LanceDB database wrapper instance.
        """
        self.embedder_config = EmbedderConfig()
        self.config = ImageConfig()
        self.img_format = self.config.format.upper()
        self.max_resolution = self.config.max_resolution

        self.clip = ClipEmbedder(
            model=clip_model, processor=clip_processor
        )
        self.unicom = UnicomImageEmbedder(
            model=unicom_model, transform=unicom_transform
        )

        self.logger = logging.getLogger(__name__)
        self.db_table = lance_db.create_or_get_collection(
            self.config.table
        )

    def ingest(self):
        """
        Main entry point for ingesting images into the database.

        This method orchestrates the ingestion process using a high-performance streaming architecture:
        1.  **Generators**: Uses a file path generator to avoid loading millions of paths into memory.
        2.  **Batching**: Chunks the stream of paths into manageable batches.
        3.  **Concurrency**: Submits batches to a ThreadPoolExecutor to process I/O and embedding in parallel.
        4.  **Sliding Window**: Manages a fixed number of active futures to keep memory usage stable.

        The process respects configuration limits (e.g., `config.limit`) and handles errors gracefully per batch.
        """
        if self.embedder_config.skip:
            self.logger.info(
                "Skipping image ingestion as per configuration."
            )
            return

        img_path_generator = self._get_images_generator(
            self.config.dir
        )

        # Check database state
        if not self.embedder_config.reset:
            # Note: We can't easily check 'count' against a generator without consuming it.
            # If strict count checking is needed, we might need a fast directory scan first.
            # For performance with large datasets, we assume we process what we find.
            pass

        self.logger.info("Starting image ingestion...")

        # Batch processing configuration
        batch_size = self.embedder_config.batch_size

        if self.config.limit:
            img_path_generator = itertools.islice(
                img_path_generator, self.config.limit
            )

        batches = self._chunked_generator(
            img_path_generator, batch_size
        )

        logging.getLogger("watchfiles").setLevel(logging.WARNING)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(
                    self._process_and_add_batch, batch
                ): batch
                for batch in itertools.islice(
                    batches, executor._max_workers * 2
                )
            }

            # As futures complete, we submit more batches
            # This implements a sliding window of active tasks
            with tqdm(
                desc="Processing batches", unit="batch"
            ) as pbar:
                while futures:
                    done, _ = concurrent.futures.wait(
                        futures,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )

                    for future in done:
                        futures.pop(future)
                        pbar.update(1)
                        try:
                            future.result()
                        except Exception as e:
                            self.logger.error(
                                f"Batch processing failed: {e}",
                                exc_info=True,
                            )

                        # Submit next batch if available
                        try:
                            next_batch = next(batches)
                            futures[
                                executor.submit(
                                    self._process_and_add_batch,
                                    next_batch,
                                )
                            ] = next_batch
                        except StopIteration:
                            pass

        self.logger.info("Image ingestion completed.")

    def _get_images_generator(
        self, img_dir: str
    ) -> Generator[str, None, None]:
        """
        Creates a generator that yields valid image file paths from a directory.

        Using `glob.iglob` instead of `glob.glob` ensures that we do not build a massive list of strings
        in memory, which is critical for datasets with millions of images.

        Args:
            img_dir (str): The root directory to scan.

        Yields:
            str: Absolute path to a valid image file.
        """
        if not os.path.isdir(img_dir):
            self.logger.error(f"Invalid image directory: {img_dir}")
            return

        valid_extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        pattern = os.path.join(img_dir, "**", "*")

        # iglob returns an iterator, avoiding building a massive list
        for f in glob.iglob(pattern, recursive=True):
            if os.path.isfile(f):
                ext = os.path.splitext(f)[1].lower()
                if ext in valid_extensions:
                    yield f

    def _chunked_generator(self, iterable, size):
        """
        Splits a source iterable into smaller lists (chunks) of a specified size.

        Args:
            iterable: The source iterable (e.g., the image path generator).
            size (int): The maximum size of each chunk.

        Yields:
            list: A list of items from the iterable.
        """
        it = iter(iterable)
        while True:
            chunk = list(itertools.islice(it, size))
            if not chunk:
                break
            yield chunk

    def _process_and_add_batch(self, img_paths: List[str]):
        """
        Orchestrates the processing of a single batch of image paths.

        Steps:
        1.  **Load & Process**: calls `_load_and_process_images` to get bytes and flags.
        2.  **Embed**: Generates embeddings using CLIP and UniCOM models.
        3.  **Format**: Constructs a Polars DataFrame with ID, bytes, format, and embeddings.
        4.  **Persist**: Merges the data into the LanceDB table.

        Args:
            img_paths (List[str]): A list of file paths to process.
        """
        if not img_paths:
            return

        # 1. Load Images & Bytes (Optimized)
        # We handle images and bytes together to avoid double iteration/opening
        successful_paths, image_bytes, original_size_flags = (
            self._load_and_process_images(img_paths)
        )

        if not successful_paths:
            return

        # 2. Compute Embeddings
        # We pass paths to embedders (assuming they handle their own loading as per original code).
        # If embedders can accept PIL images, we could optimize this further.
        try:
            clip_embeddings = self._get_all_clip_embeddings(
                successful_paths
            )
            unicom_embeddings = self._get_all_unicom_embeddings(
                successful_paths
            )
        except Exception as e:
            self.logger.error(
                f"Embedding computation failed: {e}", exc_info=True
            )
            return

        if any(e is None for e in clip_embeddings):
            self.logger.error(
                "Some embeddings failed. Skipping batch."
            )
            return

        # 3. Create DataFrame
        try:
            data = pl.DataFrame(
                {
                    "img_id": [
                        self._get_image_id(p)
                        for p in successful_paths
                    ],
                    "img_bytes": image_bytes,
                    "file_format": self.config.format,
                    "original_size": original_size_flags,
                    "clip_embeddings": clip_embeddings,
                    "unicom_embeddings": unicom_embeddings,
                }
            )

            # 4. Insert to DB
            arrow_table = data.to_arrow().cast(self.db_table.schema)
            self.db_table.merge_insert(
                "img_id"
            ).when_not_matched_insert_all().execute(arrow_table)

        except Exception as e:
            self.logger.error(
                f"Error inserting batch to DB: {e}", exc_info=True
            )

    def _load_and_process_images(
        self, img_paths: List[str]
    ) -> Tuple[List[str], List[bytes], List[bool]]:
        """
        Loads images from disk and prepares them for storage.

        **Optimization Logic:**
        This method employs a "Fast Path" optimization. It first peeks at the image metadata (format, size)
        without decoding the pixel data.
        - **Fast Path**: If the file on disk matches the target format and is within the max resolution,
          it reads the raw file bytes directly. This avoids CPU-intensive decoding and re-encoding.
        - **Slow Path**: If the file needs resizing or format conversion (e.g., PNG to WEBP, or large to small),
          it fully loads the image, processes it, and encodes it to the target format.

        Args:
            img_paths (List[str]): List of file paths.

        Returns:
            Tuple containing:
            - List[str]: Paths that were successfully processed.
            - List[bytes]: The image data as bytes.
            - List[bool]: Flags indicating if the image retained its original size (True) or was resized (False).
        """
        successful_paths = []
        valid_image_bytes = []
        all_original_size = []

        for img_path in img_paths:
            try:
                # Open lazily - does not read pixel data yet
                with Image.open(img_path) as img:
                    # --- Optimization Start ---
                    # Check if we can skip the expensive decode/resize/encode cycle
                    # We need the format on disk to match the config format (e.g., storing JPEG as JPEG)
                    # And dimensions must be within limits.
                    # We also avoid this optimization if format conversion (like PNG -> JPG) is needed for transparency handling

                    is_format_match = (
                        img.format
                        and img.format.upper() == self.img_format
                    )
                    is_within_size = (
                        max(img.size) <= self.max_resolution
                    )

                    # Basic check for transparency if we are enforcing a format that doesn't support it well (optional safety)
                    # But mainly, if we are storing as WEBP and file is WEBP, we are good.

                    if is_format_match and is_within_size:
                        # Fast path: Read file directly
                        # Reset file pointer or just read from path again safely
                        with open(img_path, "rb") as f:
                            valid_image_bytes.append(f.read())
                        all_original_size.append(True)
                        successful_paths.append(img_path)
                        continue
                    # --- Optimization End ---

                    # Slow path: Must process
                    # Convert to RGB (or RGBA for transparency handling)
                    if img.mode in ("RGBA", "LA") or (
                        img.mode == "P" and "transparency" in img.info
                    ):
                        img_loaded = img.convert("RGBA")
                    else:
                        img_loaded = img.convert("RGB")

                    # Resize if needed
                    if max(img_loaded.size) > self.max_resolution:
                        img_loaded.thumbnail(
                            (
                                self.max_resolution,
                                self.max_resolution,
                            ),
                            resample=Image.LANCZOS,
                        )
                        all_original_size.append(False)
                    else:
                        all_original_size.append(True)

                    # Save to bytes
                    img_byte_arr = io.BytesIO()
                    save_kwargs = {"format": self.img_format}
                    if self.img_format == "WEBP":
                        save_kwargs["lossless"] = True

                    img_loaded.save(img_byte_arr, **save_kwargs)
                    valid_image_bytes.append(img_byte_arr.getvalue())
                    successful_paths.append(img_path)

            except Exception as e:
                self.logger.warning(
                    f"Error processing image {img_path}: {e}"
                )
                continue

        return successful_paths, valid_image_bytes, all_original_size

    def _get_image_id(self, img_path: str) -> str:
        """Extracts the unique image ID from the file path (filename without extension)."""
        return os.path.splitext(os.path.basename(img_path))[0]

    def _get_all_clip_embeddings(
        self, img_paths: list[str]
    ) -> list[np.ndarray]:
        """Wrapper to get CLIP embeddings for a batch of images."""
        return self.clip.batch_get_embeddings(img_paths)

    def _get_all_unicom_embeddings(
        self, img_paths: list[str]
    ) -> list[np.ndarray]:
        """Wrapper to get UniCOM embeddings for a batch of images."""
        return self.unicom.batch_get_embeddings(img_paths)
