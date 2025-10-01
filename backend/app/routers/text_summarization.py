import logging
from .services.openai import AiSummary
from fastapi import (
    APIRouter,
    Request,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summarize")
async def summarize_text(request: Request, q: str):
    """
    Summarize the provided text using a text summarization service.

    Args:
        q (str): The text to be summarized.

    Returns:
        dict: A dictionary containing the summarized text or an error message.
    """
    logger.info("Received text summarization request")
    q = q.strip() if q else None
    if q is None or q == "":
        logger.warning("Text summarization query is empty")
        return {
            "error": "Query parameter 'q' is required and cannot be empty."
        }

    logger.info(
        f"Summarizing text: {q[:30]}..."
    )  # Log only the first 30 characters
    try:
        summarizer = AiSummary()
        summary = await summarizer.summarize(q)

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
