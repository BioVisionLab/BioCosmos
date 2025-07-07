import logging
from contextlib import asynccontextmanager
from .database.duckdb import init_duckdb
from fastapi import FastAPI
from .routers import image_search, text_search, taxon_search
from .database.chroma import init_db
from .services.embedder import ImageEmbeddingIngestor
from .services.embedder import ModelType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to initialize the database."""
    logger.info("Starting up the application...")
    try:
        init_duckdb()
        logger.info("DuckDB initialized successfully.")
        await init_db()
        logger.info("Database initialized successfully.")
        clip = ImageEmbeddingIngestor(model_type=ModelType.CLIP)
        await clip.process()
        unicom = ImageEmbeddingIngestor(model_type=ModelType.UNICOM)
        await unicom.process()
        logger.info("Image embedding completed successfully.")
        yield
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise e


app = FastAPI(lifespan=lifespan)

app.include_router(image_search.router)
app.include_router(text_search.router)
app.include_router(taxon_search.router)


@app.get("/")
async def root():
    logger.info("Root endpoint accessed")

    return {"message": "Welcome to the CLIP Service"}
