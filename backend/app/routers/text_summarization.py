import logging

from ..query.taxon import TaxonSearch
from fastapi import (
    APIRouter,
    Request,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summarize/{species_name}")
async def summarize_text(request: Request, species_name: str):
    """
    Summarize the provided text using a text summarization service.

    Args:
        q (str): The text to be summarized.

    Returns:
        dict: A dictionary containing the summarized text or an error message.
    """
    logger.info("Received text summarization request")
    species_name = species_name.strip() if species_name else None
    if species_name is None or species_name == "":
        logger.warning("Text summarization query is empty")
        return {
            "error": "Query parameter 'species_name' is required and cannot be empty."
        }

    logger.info(f"Summarizing text: {species_name}...")
    try:
        summarizer = TaxonSearch(request=request, query=species_name)
        summary = await summarizer.generate_summary()

        if summary is None:
            message = (
                "No summary could be generated for the provided text."
            )
            logger.info(message)
            return {"message": message}

        logger.info("Text summarization successful")
        return {"summary": summary}

    except Exception as e:
        logger.error(
            f"Error during text summarization: {e}", exc_info=True
        )
        return {
            "error": f"An error occurred while summarizing the text: {str(e)}"
        }
