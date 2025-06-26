import os
import logging
import chromadb

# --- Configuration ---
CHROMA_DB_PATH = "./chroma_db" # Directory to store Chroma data locally
CLIP_COLLECTION_NAME = "clip_collection"
UNICOM_COLLECTION_NAME = "unicom_collection"

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
        chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

        # Get or create the CLIP collection
        # No embedding function needed here if we generate embeddings manually
        clip_collection = chroma_client.get_or_create_collection(name=CLIP_COLLECTION_NAME)
        logger.info(f"Successfully connected to ChromaDB and got collection '{CLIP_COLLECTION_NAME}'.")
        logger.info(f"Collection '{CLIP_COLLECTION_NAME}' currently has {clip_collection.count()} items.")

        # Get or create the UNICOM collection
        unicom_collection = chroma_client.get_or_create_collection(name=UNICOM_COLLECTION_NAME)
        logger.info(f"Successfully connected to ChromaDB and got collection '{UNICOM_COLLECTION_NAME}'.")
        logger.info(f"Collection '{UNICOM_COLLECTION_NAME}' currently has {unicom_collection.count()} items.")
    except Exception as e:
        logger.error(f"Error initializing ChromaDB: {e}")