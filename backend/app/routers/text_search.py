from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ..services import clip

import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/text-search")
async def search_text(q: str):
    """Search for images based on a text query using CLIP embeddings.

    Args:
        q (str): The text query to search for.

    Returns:
        JSONResponse: A JSON response containing the search results or an error message.

    To query this endpoint, use:
        /text-search/?q=your+search+terms
    """
    query = q.strip()

    if query is None or query == "":
        return JSONResponse(content={"error": "Query parameter 'q' is required and cannot be empty."}, status_code=400)
    
    text_embedder = clip.ClipTextEmbedder()
    text_embedding = text_embedder.get_embedding(query)
    if text_embedding is None:
        return JSONResponse(content={"error": "Failed to compute text embedding"}, status_code=500)
    
    try:
        logger.info(f"Querying ChromaDB CLIP collection '{text_embedder.get_collection_name}'...")
        search_results = await text_embedder.query(
            query_embedding=text_embedding,
            n_results=5
        )
        logger.info("ChromaDB CLIP query completed.")

        best_hits_per_species = {}
        if (
            search_results and search_results.get('ids') and search_results['ids'][0] and
            search_results.get('metadatas') and search_results['metadatas'][0] and
            search_results.get('distances') and search_results['distances'][0]
        ):
            ids = search_results['ids'][0]
            metadatas = search_results['metadatas'][0]
            distances = search_results['distances'][0]

            for i in range(len(ids)):
                metadata = metadatas[i]
                distance = distances[i]
                hit_id = ids[i]

                if metadata and 'species_folder' in metadata and 'image_filename' in metadata:
                    species_folder = metadata['species_folder']
                    image_filename = metadata['image_filename']

                    if (
                        species_folder not in best_hits_per_species or
                        distance < best_hits_per_species[species_folder]['distance']
                    ):
                        best_hits_per_species[species_folder] = {
                            'distance': distance,
                            'best_image_filename': image_filename,
                            'id': hit_id
                        }
                else:
                    logger.warning(f"CLIP Hit {hit_id} missing 'species_folder' or 'image_filename' in metadata: {metadata}")
        else:
            logger.info("ChromaDB (CLIP) returned no results or results in unexpected format.")

        sorted_species = sorted(best_hits_per_species.items(), key=lambda item: item[1]['distance'])
        unique_results = [
            {
                "species_folder": species_folder,
                "best_image_filename": data['best_image_filename']
            }
            for species_folder, data in sorted_species
        ]
        logger.info(f"Returning {len(unique_results)} unique species results from CLIP text search.")
        return JSONResponse(content=unique_results)
    except Exception as e:
        logger.error(f"Error during CLIP text search for query '{query}': {e}", exc_info=True)
        return JSONResponse(content={"error": "An internal error occurred during text search."}, status_code=500)
