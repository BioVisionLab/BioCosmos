import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .routers import image_search, text_search
from .services.chroma import init_db
from .services.embedder import ImageEmbedder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to initialize the database."""
    logger.info("Starting up the application...")
    try:
        await init_db()
        logger.info("Database initialized successfully.")
        embedder = ImageEmbedder()
        await embedder.batch_embed_images()
        logger.info("Image embedding completed successfully.")
        yield
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise e
    


app = FastAPI(lifespan=lifespan)

app.include_router(image_search.router)
app.include_router(text_search.router)


@app.get("/")
async def root():
    logger.info("Root endpoint accessed")

    return {"message": "Welcome to the CLIP Service"}
