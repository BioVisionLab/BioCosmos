from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
from ..services import unicom

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/img-search")
async def image_search(request: Request):
    """ """

    logger.info("Received image search request (UNICOM).")
    try:
        data = await request.json()
        if not data or "image" not in data:
            logger.warning(
                "Image search request missing 'image' field in JSON body."
            )
            return JSONResponse(
                content={
                    "error": "Missing 'image' field in JSON body"
                },
                status_code=400,
            )

        base64_image = data["image"]

        # 1. Get image embedding from base64 using UNICOM
        logger.info(
            "Generating UNICOM image embedding from base64 data..."
        )
        embedder = unicom.UnicomImageEmbedder()
        if embedder.model is None:
            logger.error(
                "UNICOM model is not available for image embedding."
            )
            return JSONResponse(
                content={
                    "error": "UNICOM model is not available for image embedding."
                },
                status_code=500,
            )
        query_embeddings = embedder.get_embedding(base64_image)
        if query_embeddings is None:
            # Error logged in helper function
            return JSONResponse(
                content={
                    "error": "Failed to process uploaded image using UNICOM."
                },
                status_code=400,
            )
        logger.info("UNICOM image embedding generated.")

        # 2. Search UNICOM ChromaDB collection
        logger.info(
            f"Querying ChromaDB UNICOM collection '{embedder.get_collection_name}' with image embedding..."
        )
        search_results = await embedder.query(
            query_embedding=query_embeddings, n_results=5
        )
        logger.info("ChromaDB UNICOM query completed.")

        # 3. Process results (same logic as text search)
        best_hits_per_species = {}
        if (
            search_results
            and search_results["ids"]
            and search_results["ids"][0]
            and search_results["metadatas"]
            and search_results["metadatas"][0]
            and search_results["distances"]
            and search_results["distances"][0]
        ):
            ids = search_results["ids"][0]
            metadatas = search_results["metadatas"][0]
            distances = search_results["distances"][0]

            for i in range(len(ids)):
                metadata = metadatas[i]
                distance = distances[i]
                hit_id = ids[i]
                if (
                    metadata
                    and "species_folder" in metadata
                    and "image_filename" in metadata
                ):
                    species_folder = metadata["species_folder"]
                    image_filename = metadata["image_filename"]
                    # Keep track of the best hit (lowest distance) for each species_folder
                    if (
                        species_folder not in best_hits_per_species
                        or distance
                        < best_hits_per_species[species_folder][
                            "distance"
                        ]
                    ):
                        best_hits_per_species[species_folder] = {
                            "distance": distance,
                            "best_image_filename": image_filename,
                            "id": hit_id,
                        }
                else:
                    logger.warning(
                        f"UNICOM Hit {hit_id} missing 'species_folder' or 'image_filename' in metadata: {metadata}"
                    )
        else:
            logger.info(
                "ChromaDB (UNICOM) returned no results or results in unexpected format for image search."
            )

        # 4. Extract results (same logic as text search)
        sorted_species = sorted(
            best_hits_per_species.items(),
            key=lambda item: item[1]["distance"],
        )
        unique_results = [
            {
                "species_folder": species_folder,
                "best_image_filename": data["best_image_filename"],
            }
            for species_folder, data in sorted_species
        ]
        logger.info(
            f"Returning {len(unique_results)} unique species results from UNICOM image search."
        )
        return JSONResponse(content=unique_results, status_code=200)

    except Exception as e:
        logger.error(
            f"Error during UNICOM image search: {e}", exc_info=True
        )
        return JSONResponse(
            content={
                "error": "An internal error occurred during image search."
            },
            status_code=500,
        )
