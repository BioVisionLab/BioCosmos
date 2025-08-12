import os
import logging
import chromadb
from .model import ImageData

CHROMA_DB_PATH = "./chroma_db"

BATCH_SIZE = 32

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def init_chroma():
    logger.info(
        f"Initializing ChromaDB client with path: {CHROMA_DB_PATH}..."
    )
    try:
        if not os.path.exists(CHROMA_DB_PATH):
            os.makedirs(CHROMA_DB_PATH)
            logger.info(
                f"Created ChromaDB directory: {CHROMA_DB_PATH}"
            )
        await get_client()
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


async def query_collection(
    collection_name, query_embedding, n_results=5
):
    """Query the CLIP collection in ChromaDB."""
    logger.info(
        f"Querying ChromaDB CLIP collection '{collection_name}'..."
    )
    client = await get_client()
    if not client:
        logger.error("ChromaDB client is not available.")
        return None

    collection = client.get_or_create_collection(name=collection_name)

    try:
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=["metadatas", "distances"],
        )
        logger.info("ChromaDB CLIP query completed.")
        return results
    except Exception as e:
        logger.error(
            f"Error querying CLIP collection: {e}", exc_info=True
        )
        return None


async def upsert_to_chroma(
    collection_name: str, img_data: list[ImageData]
):
    """Upsert embeddings into ChromaDB."""
    data_size = len(img_data)
    logger.info(
        f"Inserting {data_size} embeddings to ChromaDB collection '{collection_name}'..."
    )
    client = await get_client()
    if not client:
        logger.error("ChromaDB client is not available.")
        return
    collection = client.get_or_create_collection(name=collection_name)

    num_batches = data_size // BATCH_SIZE + (
        1 if data_size % BATCH_SIZE > 0 else 0
    )
    for i in range(num_batches):
        start_idx = i * BATCH_SIZE
        end_idx = min((i + 1) * BATCH_SIZE, data_size)
        batch_data = img_data[start_idx:end_idx]

        # Extract ids, embeddings, and metadata from batch_data
        batch_ids = [item.metadata.unique_id for item in batch_data]
        batch_embeddings = [item.embedding for item in batch_data]
        batch_metadata = [
            item.metadata.to_dict() for item in batch_data
        ]

        try:
            logger.info(
                f"Adding batch {i + 1}/{num_batches} (size {len(batch_data)})..."
            )
            collection.upsert(
                ids=batch_ids,
                embeddings=batch_embeddings,
                metadatas=batch_metadata,
            )
        except Exception as e:
            logger.error(
                f"Error adding batch {i + 1} to ChromaDB: {e}",
                exc_info=True,
            )

    logger.info("Finished adding embeddings to ChromaDB.")
    logger.info(
        f"Final item count in collection '{collection_name}': {collection.count()}"
    )
