import torch
import logging
import unicom
import chromadb
from PIL import Image
from chromadb.utils.batch_utils import create_batches  # Utility for batching
import os
import glob

IMAGE_BASE_DIR = "../public/images/nymphalidae_new" # Relative path from clip_service folder
CHROMA_DB_PATH = "./chroma_db" # Directory to store Chroma data locally
# Use UNICOM specific names
COLLECTION_NAME = "biocosmos_images_unicom"
MODEL_NAME = "ViT-L/14@336px"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 32 # UNICOM ViT-L is larger, might need smaller batch size

logger = logging.getLogger(__name__)


class ImageEmbedder:
    def __init__(self, model_name=MODEL_NAME, device=DEVICE):
        self.model_name = model_name
        self.device = device
        self.model, self.transform = self.load_model()

    def get_images(self, image_dir=IMAGE_BASE_DIR):
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
                    embedding = self.model.encode_image(image_tensor)
                # We normalize the embedding to unit length
                # which is useful for cosine similarity search
                embedding /= embedding.norm(dim=-1, keepdim=True)
                embeddings.append(embedding.cpu().numpy())
            except Exception as e:
                logger.error(f"Error processing image {image_path}: {e}")
        return embeddings
    
    def embed_images(self, batch, embeddings):
        """Embed all images in the specified directory."""
        image_paths = self.get_images()
        logger.info(f"Found {len(image_paths)} images to embed.")

        all_embeddings = []
        all_ids = []
        all_metadata = []
        processed_image_count = 0
        skipped_image_count = 0

        for batch in create_batches(image_paths, BATCH_SIZE):
            batch_embeddings = self.get_embeddings(batch)
            for img_path, embedding in zip(batch, batch_embeddings):
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

            if (processed_image_count + skipped_image_count) % 100 == 0:
                logger.info(f"Processed {(processed_image_count + skipped_image_count)} images for UNICOM...")

        return all_ids, all_embeddings, all_metadata
    
    def upsert_to_chroma(self, ids, embeddings, metadata):
        """Upsert embeddings into ChromaDB."""
        client = chromadb.Client(chromadb.PersistentClient(path=CHROMA_DB_PATH))
        collection = client.get_or_create_collection(COLLECTION_NAME)
        
        # Upsert the embeddings
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadata
        )
        logger.info(f"Upserted {len(ids)} embeddings to ChromaDB collection '{COLLECTION_NAME}'.")
