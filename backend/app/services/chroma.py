import os
import logging
from tkinter import Image
import chromadb
from .model import ImageData

# --- Configuration ---
CHROMA_DB_PATH = "./chroma_db" # Directory to store Chroma data locally


# # Use UNICOM specific names
# COLLECTION_NAME = "biocosmos_images_unicom"
BATCH_SIZE = 32

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def init_db():
    logger.info(f"Initializing ChromaDB client with path: {CHROMA_DB_PATH}...")
    try:
        # Ensure the directory exists
        if not os.path.exists(CHROMA_DB_PATH):
            os.makedirs(CHROMA_DB_PATH)
            logger.info(f"Created ChromaDB directory: {CHROMA_DB_PATH}")

        # Initialize persistent client
        chroma_client = await get_client()

        # # Get or create the CLIP collection
        # # No embedding function needed here if we generate embeddings manually
        # clip_collection = chroma_client.get_or_create_collection(name=CLIP_COLLECTION_NAME)
        # logger.info(f"Successfully connected to ChromaDB and got collection '{CLIP_COLLECTION_NAME}'.")
        # logger.info(f"Collection '{CLIP_COLLECTION_NAME}' currently has {clip_collection.count()} items.")

        # # Get or create the UNICOM collection
        # unicom_collection = chroma_client.get_or_create_collection(name=UNICOM_COLLECTION_NAME)
        # logger.info(f"Successfully connected to ChromaDB and got collection '{UNICOM_COLLECTION_NAME}'.")
        # logger.info(f"Collection '{UNICOM_COLLECTION_NAME}' currently has {unicom_collection.count()} items.")
    except Exception as e:
        logger.error(f"Error initializing ChromaDB: {e}")

async def get_client():
    """Get the ChromaDB client."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        return client
    except Exception as e:
        logger.error(f"Error getting ChromaDB client: {e}")
        return None

async def query_collection(collection_name, query_embedding, n_results=5):
    """Query the CLIP collection in ChromaDB."""
    logger.info(f"Querying ChromaDB CLIP collection '{collection_name}'...")
    client = await get_client()
    if not client:
        logger.error("ChromaDB client is not available.")
        return None
    
    collection = client.get_or_create_collection(name=collection_name)
    
    try:
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=['metadatas', 'distances']
        )
        logger.info("ChromaDB CLIP query completed.")
        return results
    except Exception as e:
        logger.error(f"Error querying CLIP collection: {e}", exc_info=True)
        return None
   
async def upsert_to_chroma(collection_name: str, img_data: list[ImageData]):
    """Upsert embeddings into ChromaDB."""
    data_size = len(img_data)
    logger.info(f"Inserting {data_size} embeddings to ChromaDB collection '{collection_name}'...")
    client =  await get_client()
    if not client:
        logger.error("ChromaDB client is not available.")
        return
    collection = client.get_or_create_collection(name=collection_name)
    
    # Use upsert=True to avoid errors if an ID already exists (e.g., re-running the script)
    num_batches = data_size // BATCH_SIZE + (1 if data_size % BATCH_SIZE > 0 else 0)
    for i in range(num_batches):
        start_idx = i * BATCH_SIZE
        end_idx = min((i + 1) * BATCH_SIZE, data_size)
        batch_data = img_data[start_idx:end_idx]

        # Extract ids, embeddings, and metadata from batch_data
        batch_ids = [item.metadata.unique_id for item in batch_data]
        batch_embeddings = [item.embedding for item in batch_data]
        batch_metadata = [item.metadata.to_dict() for item in batch_data]
        
        try:
            logger.info(f"Adding batch {i+1}/{num_batches} (size {len(batch_data)})...")
            collection.upsert(
                ids=batch_ids,           
                embeddings=batch_embeddings,
                metadatas=batch_metadata
            )                      
        except Exception as e:
            logger.error(f"Error adding batch {i+1} to ChromaDB: {e}", exc_info=True)
            # Consider stopping or continuing on batch error
            # continue 

    logger.info("Finished adding embeddings to ChromaDB.")
    logger.info(f"Final item count in collection '{collection_name}': {collection.count()}")
    