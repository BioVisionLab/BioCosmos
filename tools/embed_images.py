import os
import glob
import logging
import torch
from PIL import Image
# Remove transformers imports, add unicom import
# from transformers import AutoImageProcessor, AutoModel 
import unicom
import chromadb
from chromadb.utils.batch_utils import create_batches # Utility for batching

# --- Configuration ---
IMAGE_BASE_DIR = "../public/images/nymphalidae_new" # Relative path from clip_service folder
CHROMA_DB_PATH = "./chroma_db" # Directory to store Chroma data locally
# Use UNICOM specific names
COLLECTION_NAME = "biocosmos_images_unicom"
MODEL_NAME = "ViT-L/14@336px"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 32 # UNICOM ViT-L is larger, might need smaller batch size

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Load UNICOM Model and Transform ---
logger.info(f"Loading UNICOM model: {MODEL_NAME}...")
try:
    # Load UNICOM model (likely defaults to CPU) and transform
    _model, transform = unicom.load(MODEL_NAME) # Load without specifying device initially
    # Explicitly move the entire model to the target device
    model = _model.to(DEVICE)
    model.eval() # Set model to evaluation mode
    logger.info(f"UNICOM model and transform loaded and moved to {DEVICE} successfully")
except Exception as e:
    logger.error(f"Fatal error loading or moving UNICOM model: {e}", exc_info=True)
    exit(1)

# --- Initialize ChromaDB ---
logger.info(f"Initializing ChromaDB client at path: {CHROMA_DB_PATH}...")
try:
    if not os.path.exists(CHROMA_DB_PATH):
        os.makedirs(CHROMA_DB_PATH)
        logger.info(f"Created ChromaDB directory: {CHROMA_DB_PATH}")
    
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    
    # Get or create the UNICOM collection
    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
    logger.info(f"Connected to ChromaDB. Collection '{COLLECTION_NAME}' ready.")
    logger.info(f"Initial item count: {collection.count()}")
except Exception as e:
    logger.error(f"Fatal error connecting to ChromaDB: {e}", exc_info=True)
    exit(1)

# --- Helper Function for UNICOM Image Embedding ---
def get_image_embedding(image_path):
    try:
        image = Image.open(image_path).convert("RGB")
        # Apply UNICOM's transform and add batch dimension
        image_tensor = transform(image).unsqueeze(0).to(DEVICE)
        
        with torch.no_grad():
            # Get UNICOM embedding
            image_features = model(image_tensor)
        
        # Normalize (important for cosine similarity)
        image_features /= image_features.norm(dim=-1, keepdim=True) 
        
        # Return as flat list for ChromaDB
        return image_features.cpu().numpy().flatten().tolist() 
    except Exception as e:
        logger.warning(f"Could not process image {image_path} with UNICOM: {e}")
        return None

# --- Main Embedding Process ---
def embed_all_images():
    logger.info(f"Starting UNICOM image embedding process from directory: {IMAGE_BASE_DIR}")
    species_folders = [d for d in os.listdir(IMAGE_BASE_DIR) if os.path.isdir(os.path.join(IMAGE_BASE_DIR, d))]
    logger.info(f"Found {len(species_folders)} species folders.")

    all_embeddings = []
    all_metadatas = []
    all_ids = []
    processed_image_count = 0
    skipped_image_count = 0

    for folder_name in species_folders:
        folder_path = os.path.join(IMAGE_BASE_DIR, folder_name)
        # Find common image types
        image_paths = glob.glob(os.path.join(folder_path, '*.jpg')) + \
                      glob.glob(os.path.join(folder_path, '*.jpeg')) + \
                      glob.glob(os.path.join(folder_path, '*.png')) + \
                      glob.glob(os.path.join(folder_path, '*.webp'))
        
        logger.info(f"Processing {len(image_paths)} images in folder '{folder_name}' for UNICOM embeddings...")

        for img_path in image_paths:
            embedding = get_image_embedding(img_path) # Uses the updated helper
            if embedding:
                all_embeddings.append(embedding)
                filename = os.path.basename(img_path)
                # Create a unique ID, e.g., foldername_filename
                unique_id = f"{folder_name}_{filename}"
                all_ids.append(unique_id)
                all_metadatas.append({
                    "species_folder": folder_name,
                    "image_filename": filename
                })
                processed_image_count += 1
            else:
                skipped_image_count += 1
            
            # Log progress periodically
            if (processed_image_count + skipped_image_count) % 100 == 0:
                 logger.info(f"Processed {(processed_image_count + skipped_image_count)} images for UNICOM...")

    logger.info(f"Generated {len(all_embeddings)} UNICOM embeddings successfully.")
    logger.info(f"Skipped {skipped_image_count} images due to errors.")

    if not all_embeddings:
        logger.info("No UNICOM embeddings generated. Exiting.")
        return

    # --- Add UNICOM Embeddings to ChromaDB in Batches ---
    logger.info(f"Adding {len(all_ids)} UNICOM embeddings to ChromaDB collection '{COLLECTION_NAME}' in batches of {BATCH_SIZE}...")
    
    # Use upsert=True to avoid errors if an ID already exists (e.g., re-running the script)
    num_batches = len(all_ids) // BATCH_SIZE + (1 if len(all_ids) % BATCH_SIZE > 0 else 0)
    for i in range(num_batches):
        start_idx = i * BATCH_SIZE
        end_idx = min((i + 1) * BATCH_SIZE, len(all_ids))
        batch_ids = all_ids[start_idx:end_idx]
        batch_embeddings = all_embeddings[start_idx:end_idx]
        batch_metadatas = all_metadatas[start_idx:end_idx]
        
        try:
            logger.info(f"Adding UNICOM batch {i+1}/{num_batches} (size {len(batch_ids)})...")
            collection.upsert( # Target collection is already set to the UNICOM one
                ids=batch_ids,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas
            )
        except Exception as e:
            logger.error(f"Error adding UNICOM batch {i+1} to ChromaDB: {e}", exc_info=True)
            # Consider stopping or continuing on batch error
            # continue 

    logger.info("Finished adding UNICOM embeddings to ChromaDB.")
    logger.info(f"Final item count in UNICOM collection '{COLLECTION_NAME}': {collection.count()}")

# --- Run the Embedding Process ---
if __name__ == '__main__':
    embed_all_images() 