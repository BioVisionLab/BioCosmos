import torch
import logging
from PIL import Image  # Utility for batching
import os
import glob
from tqdm import tqdm
from .chroma import upsert_to_chroma, get_client  # Assuming chroma.py contains the ChromaDB initialization and upsert logic
import numpy as np
from enum import Enum
from .unicom import UnicomImageEmbedder
from .clip import ClipTextEmbedder

IMAGE_BASE_DIR = "../public/images/nymphalidae_new" # Relative path from clip_service folder
CHROMA_DB_PATH = "./chroma_db" # Directory to store Chroma data locally

if torch.backends.mps.is_available():
    DEVICE = "mps"
elif torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"
BATCH_SIZE = 32 # UNICOM ViT-L is larger, might need smaller batch size

logger = logging.getLogger(__name__)

class ModelType(Enum):
    UNICOM = 1
    CLIP = 2

class ImageEmbeddingIngestor:
    def __init__(self,  model_type, img_dir=IMAGE_BASE_DIR):
        """Initialize model and device for image embedding."""
        self.img_dir = img_dir
        self.model_type = model_type
    
    def get_embedding(self, img_paths):
        """Get embeddings for a list of image paths."""

        match self.model_type:
            case ModelType.UNICOM:
                logger.info(f"Getting UNICOM embeddings for {len(img_paths)} images.")
                embedding = UnicomImageEmbedder().get_image_embedding(img_paths)
                return embedding if embedding is not None else None
                    
            case ModelType.CLIP:
                logger.info(f"Getting CLIP embeddings for {len(img_paths)} images.")
                embedding = ClipTextEmbedder ().get_image_embedding(img_paths)
                return embedding if embedding is not None else None
            
    def embed_clip(self, img_paths):
        """Embed images using CLIP model."""
        logger.info(f"Found {len(img_paths)} images to embed.")

        embeddings = []
        all_ids = []
        all_metadata = []

        processed_image_count = 0
        skipped_image_count = 0

        total_images = len(img_paths)
        with tqdm(total=total_images, desc="Embedding images") as progress_bar:
            for img_path in img_paths:
                if not os.path.isfile(img_path):
                    logger.warning(f"Image file not found: {img_path}")
                    skipped_image_count += 1
                    progress_bar.update(1)
                    continue
                try:
                    embedding = self.get_embedding([img_path])
                    if embedding is not None:
                        embeddings.append(embedding)
                        filename = os.path.basename(img_path)
                        folder_name = os.path.basename(os.path.dirname(img_path))
                        unique_id = f"{folder_name}_{filename}"
                        all_ids.append(unique_id)
                        all_metadata.append({
                            "species_folder": folder_name,
                            "image_filename": filename
                        })
                        processed_image_count += 1
                    else:
                        skipped_image_count += 1
                except Exception as e:
                    logger.error(f"Error processing image {img_path}: {e}", exc_info=True)
                    skipped_image_count += 1
                    progress_bar.update(1)
                    continue
                
                progress_bar.update(1)

        return all_ids, embeddings, all_metadata

    def embed_unicom(self, img_paths):
        """Embed images using UNICOM model."""
        logger.info(f"Found {len(img_paths)} images to embed.")

        embeddings = []
        all_ids = []
        all_metadata = []

        processed_image_count = 0
        skipped_image_count = 0

        total_images = len(img_paths)
        with tqdm(total=total_images, desc="Embedding images") as progress_bar:
            for img_path in img_paths:
                if not os.path.isfile(img_path):
                    logger.warning(f"Image file not found: {img_path}")
                    skipped_image_count += 1
                    progress_bar.update(1)
                    continue
                try:
                    embedding = self.get_embedding([img_path])
                    if embedding is not None:
                        embeddings.append(embedding)
                        filename = os.path.basename(img_path)
                        folder_name = os.path.basename(os.path.dirname(img_path))
                        unique_id = f"{folder_name}_{filename}"
                        all_ids.append(unique_id)
                        all_metadata.append({
                            "species_folder": folder_name,
                            "image_filename": filename
                        })
                        processed_image_count += 1
                    else:
                        skipped_image_count += 1
                except Exception as e:
                    logger.error(f"Error processing image {img_path}: {e}", exc_info=True)
                    skipped_image_count += 1
                    progress_bar.update(1)
                    continue
                
                progress_bar.update(1)

        return all_ids, embeddings, all_metadata
    
    async def filter_new_images_from_db(self, all_ids):
        """Filter out images that are already in the ChromaDB."""
        client = await get_client()
        if not client:
            logger.error("ChromaDB client is not available.")
            return all_ids
        collection = client.get_or_create_collection(name="CLIP_COLLECTION_NAME")
        existing_ids = set(collection.get()['ids'])
        new_ids = [img_id for img_id in all_ids if img_id not in existing_ids]
        if len(new_ids) < len(all_ids):
            logger.info(f"Filtered out {len(all_ids) - len(new_ids)} existing images from {len(all_ids)} total images.")
        else:
            logger.info("No existing images found in ChromaDB, all images will be processed.")
        return new_ids[100]

    async def process(self):
        """Main method to embed images in batches and store in ChromaDB."""
        logger.info(f"Starting CLIP image embedding process from directory: {self.img_dir}")
        image_paths = self.get_images()
        logger.info(f"Found {len(image_paths)} images to process.")
        # we only process first 50 for testing purposes
        # filter  out images that are already in the database
        image_paths = await self.filter_new_images_from_db(image_paths)
        all_ids, all_embeddings, all_metadata = self.embed_images(image_paths)

        if all_ids:
            await upsert_to_chroma(all_ids, all_embeddings, all_metadata)
            logger.info("Embedding and upsert completed successfully.")
        else:
            logger.warning("No valid images found for embedding.")