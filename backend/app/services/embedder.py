import torch
import logging
import unicom  # Assuming UNICOM is a library for the ViT-L model
from PIL import Image  # Utility for batching
import os
import glob
from tqdm import tqdm
from .chroma import upsert_to_chroma, get_client  # Assuming chroma.py contains the ChromaDB initialization and upsert logic
import numpy as np

IMAGE_BASE_DIR = "../public/images/nymphalidae_new" # Relative path from clip_service folder
CHROMA_DB_PATH = "./chroma_db" # Directory to store Chroma data locally

MODEL_NAME = "ViT-L/14@336px"
if torch.backends.mps.is_available():
    DEVICE = "mps"
elif torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"
BATCH_SIZE = 32 # UNICOM ViT-L is larger, might need smaller batch size

logger = logging.getLogger(__name__)


class ImageEmbedder:
    def __init__(self, model_name=MODEL_NAME, device=DEVICE):
        self.model_name = model_name
        self.device = device
        self.model, self.transform = self.load_model()
    
    def load_model(self):
        """Load the UNICOM model and its transform."""
        logger.info(f"Loading UNICOM model: {self.model_name}...")
        try:
            # Load UNICOM model (likely defaults to CPU) and transform
            _model, transform = unicom.load(self.model_name)  # Load without specifying device initially
            # Explicitly move the entire model to the target device
            model = _model.to(self.device)
            model.eval()  # Set model to evaluation mode
            logger.info(f"UNICOM model and transform loaded and moved to {self.device} successfully")
            return model, transform
        except Exception as e:
            logger.error(f"Fatal error loading or moving UNICOM model: {e}", exc_info=True)
            raise e

    def get_images(self, image_dir):
        """Get all image file paths from the specified directory."""
        exts = ('.jpg', '.jpeg', '.png', '.webp')
        return [
            f for f in glob.glob(f"{image_dir}/**/*", recursive=True)
            if os.path.isfile(f) and f.lower().endswith(exts)
        ]

    def get_embeddings(self, image_paths):
        """Get embeddings for a list of image paths."""
        embeddings = []
        for image_path in image_paths:
            try:
                image = Image.open(image_path).convert("RGB")
                image_tensor = self.transform(image).unsqueeze(0).to(self.device)
                with torch.no_grad():
                    # Use the correct method for UNICOM model inference
                    embedding = self.model(image_tensor)
                # We normalize the embedding to unit length
                # which is useful for cosine similarity search
                embedding /= embedding.norm(dim=-1, keepdim=True)
                embeddings.append(embedding.cpu().numpy().flatten().tolist())
            except Exception as e:
                logger.error(f"Error processing image {image_path}: {e}")
        return embeddings
    
    # Fallback batching if create_batches fails due to ChromaDB API dependency
    def simple_batches(self, lst, batch_size):
        for i in range(0, len(lst), batch_size):
            yield lst[i:i + batch_size]

    def embed_images(self, image_paths):
        """Embed all images in the specified directory."""
        logger.info(f"Found {len(image_paths)} images to embed.")

        all_embeddings = []
        all_ids = []
        all_metadata = []
        processed_image_count = 0
        skipped_image_count = 0

        total_images = len(image_paths)
        with tqdm(total=total_images, desc="Embedding images") as pbar:
            for batch in self.simple_batches(image_paths, BATCH_SIZE):
                embeddings = self.get_embeddings(batch)
                for img_path, embedding in zip(batch, embeddings):
                    if embedding is not None:
                        all_embeddings.append(embedding)
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
                    pbar.update(1)

        return all_ids, all_embeddings, all_metadata
    
    async def filter_new_images_from_db(self, all_ids):
        """Filter out images that are already in the ChromaDB."""
        client = await get_client()
        if not client:
            logger.error("ChromaDB client is not available.")
            return all_ids
        collection = client.get_or_create_collection(name="UNICOM_COLLECTION_NAME")
        existing_ids = set(collection.get()['ids'])
        new_ids = [img_id for img_id in all_ids if img_id not in existing_ids]
        if len(new_ids) < len(all_ids):
            logger.info(f"Filtered out {len(all_ids) - len(new_ids)} existing images from {len(all_ids)} total images.")
        else:
            logger.info("No existing images found in ChromaDB, all images will be processed.")
        return new_ids[500]

    async def batch_embed_images(self, image_dir=IMAGE_BASE_DIR):
        """Main method to embed images in batches and store in ChromaDB."""
        logger.info(f"Starting UNICOM image embedding process from directory: {image_dir}")
        image_paths = self.get_images(image_dir)
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