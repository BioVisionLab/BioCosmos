import logging
import os
import chromadb
import numpy as np
from sklearn.manifold import TSNE
import pickle
import time

# --- Configuration ---
CHROMA_DB_PATH = "./chroma_db" # Directory where ChromaDB data is stored
COLLECTION_NAME = "biocosmos_images_unicom" # The UNICOM embeddings collection
OUTPUT_FILE = "./tsne_outputs/unicom_tsne_coords.pkl" # File to save the results
# t-SNE Parameters (tune these based on your dataset and desired output)
TSNE_PERPLEXITY = 30 
TSNE_N_ITER = 1000 # Minimum iterations for stabilization
TSNE_INIT = 'pca' # PCA initialization is often faster and more stable
TSNE_LEARNING_RATE = 'auto' # Recommended setting for scikit-learn >= 1.1
TSNE_N_JOBS = -1 # Use all available CPU cores
RANDOM_STATE = 42 # For reproducibility

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Main Function ---
def generate_tsne():
    logger.info("--- Starting t-SNE Coordinate Generation ---")
    
    # --- 1. Connect to ChromaDB ---
    logger.info(f"Connecting to ChromaDB at path: {CHROMA_DB_PATH}...")
    try:
        if not os.path.exists(CHROMA_DB_PATH):
             logger.error(f"ChromaDB path not found: {CHROMA_DB_PATH}")
             return
        chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = chroma_client.get_collection(name=COLLECTION_NAME)
        logger.info(f"Successfully connected to collection '{COLLECTION_NAME}'.")
        collection_count = collection.count()
        logger.info(f"Collection contains {collection_count} items.")
        if collection_count == 0:
            logger.error("Collection is empty. Cannot generate t-SNE. Did the embedding script run successfully?")
            return
            
    except Exception as e:
        logger.error(f"Error connecting to ChromaDB: {e}", exc_info=True)
        return

    # --- 2. Fetch Embeddings, IDs, and Metadata ---
    logger.info("Fetching all embeddings, IDs, and metadatas from the collection...")
    try:
        # Fetch all items. Note: Loads all into memory.
        results = collection.get(include=['embeddings', 'metadatas']) 
        embeddings = results['embeddings']
        ids = results['ids']
        metadatas = results['metadatas'] # <-- Get metadatas
        
        # Correct check: Verify if the list of IDs is empty
        if not ids:
             logger.error("Failed to retrieve IDs (and likely embeddings/metadata) from the collection.")
             return
        # Optional safety checks
        if not metadatas or len(metadatas) != len(ids):
             logger.error(f"Mismatch or missing metadata. IDs: {len(ids)}, Metadatas: {len(metadatas) if metadatas else 0}")
             return
        if len(embeddings) != len(ids):
            logger.error(f"Mismatch between number of embeddings ({len(embeddings)}) and IDs ({len(ids)}). Aborting.")
            return
             
        logger.info(f"Successfully fetched {len(ids)} embeddings and metadatas.")
        
        # Convert embeddings to a NumPy array
        embeddings_array = np.array(embeddings, dtype=np.float32)
        logger.info(f"Embeddings array shape: {embeddings_array.shape}")

    except Exception as e:
        logger.error(f"Error fetching data from ChromaDB: {e}", exc_info=True)
        return

    # --- 3. Run t-SNE ---
    logger.info(f"Starting t-SNE calculation (perplexity={TSNE_PERPLEXITY}, n_iter={TSNE_N_ITER})...")
    start_time = time.time()
    try:
        tsne = TSNE(
            n_components=2, 
            perplexity=TSNE_PERPLEXITY, 
            n_iter=TSNE_N_ITER,
            init=TSNE_INIT,
            learning_rate=TSNE_LEARNING_RATE,
            random_state=RANDOM_STATE, 
            n_jobs=TSNE_N_JOBS,
            verbose=1 # Print progress updates
        )
        tsne_coords = tsne.fit_transform(embeddings_array)
        end_time = time.time()
        logger.info(f"t-SNE calculation finished in {end_time - start_time:.2f} seconds.")
        logger.info(f"Resulting coordinates array shape: {tsne_coords.shape}")

    except Exception as e:
        logger.error(f"Error during t-SNE calculation: {e}", exc_info=True)
        return

    # --- 4. Save Results ---
    logger.info(f"Saving results to {OUTPUT_FILE}...")
    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(OUTPUT_FILE)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")
            
        # Save IDs, coordinates, AND metadatas together
        output_data = {'ids': ids, 'coords': tsne_coords, 'metadatas': metadatas}
        
        with open(OUTPUT_FILE, 'wb') as f:
            pickle.dump(output_data, f)
        
        logger.info("Successfully saved t-SNE coordinates, IDs, and metadatas.")

    except Exception as e:
        logger.error(f"Error saving results: {e}", exc_info=True)
        return

    logger.info("--- t-SNE Coordinate Generation Complete ---")

# --- Run the Process ---
if __name__ == '__main__':
    generate_tsne() 