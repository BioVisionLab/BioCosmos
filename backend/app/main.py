import logging
from contextlib import asynccontextmanager
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database.duckdb import DuckDBClient
from .services.unicom import UnicomModel
from .database.lance import LanceDB
from .services.clip import ClipModel
from .services.embedder import ImageEmbedder
from .services.umap import SpeciesImageUmap
from .services.image_meta import ImageMetaService
from .services.gbif import GbifPersistData
from .services.leptraits import LepTraits
from .routers import (
    data_stats,
    image_retrieval,
    ml_search,
    species_data,
    text_summarization,
    db_search,
    agent_search,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

description = """
This is the backend API for the BIOCOSMOS project, providing endpoints for
image search, taxon data retrieval, and text summarization using machine
learning models like CLIP and UNICOM.
"""

tags_metadata = [
    {
        "name": "ML Search",
        "description": "Machine learning-based search for images using text or image queries.",
    },
    {
        "name": "Conventional Search",
        "description": "Conventional database search for taxon information.",
    },
    {
        "name": "Data Statistics",
        "description": "Get various statistics about the database including taxon counts.",
    },
    {
        "name": "Species Data",
        "description": "Get species-related data including species, specimen data, and image IDs.",
    },
    {
        "name": "Taxon Images",
        "description": "Retrieve images by their IDs, including thumbnails and full-resolution images.",
    },
    {
        "name": "Server Health",
        "description": "Endpoints for checking the health status of the server.",
    },
]


class AppSettings(BaseSettings):
    """
    Manages application settings and environment variables using Pydantic.
    This centralizes configuration and provides validation.
    """

    DUCK_DIR: str
    LANCE_DIR: str
    IMAGE_DIR: str
    GBIF_DIR: str
    LLM_API_URL: str
    LLM_API_KEY: str
    IMAGE_META_DIR: str
    GBIF_DIR: str
    UMAP_DIR: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # optional: ignore unexpected keys
    )


def get_app_settings() -> AppSettings:
    """
    Loads and validates application settings.
    Raises an EnvironmentError if required settings are missing.
    """
    try:
        return AppSettings()
    except ValidationError as e:
        missing_vars = [
            err["loc"][0] for err in e.errors() if "loc" in err
        ]
        error_message = f"Missing or invalid required environment variables: {', '.join(missing_vars)}"
        logger.error(error_message)
        raise EnvironmentError(error_message) from e


def initialize_models(app: FastAPI):
    """Initializes and attaches machine learning models to the app state."""
    logger.info("Initializing CLIP model...")
    clip_model, clip_processor = ClipModel.load_model()
    app.state.clip_embedder = ClipModel(
        model=clip_model, processor=clip_processor
    )
    logger.info("CLIP model initialized successfully.")

    logger.info("Initializing UNICOM model...")
    unicom_model, unicom_transform = UnicomModel.load_model()
    app.state.unicom_embedder = UnicomModel(
        model=unicom_model, transform=unicom_transform
    )
    logger.info("UNICOM model initialized successfully.")


def initialize_lance(app: FastAPI):
    """Initializes and attaches the database to the app state."""
    logger.info("Initializing LanceDB...")
    app.state.lance_db = LanceDB()
    logger.info("LanceDB initialized successfully.")


def initialize_duckdb(app: FastAPI):
    """Initializes and attaches the DuckDB to the app state."""
    logger.info("Initializing DuckDB...")
    app.state.duck_db = DuckDBClient()
    logger.info("DuckDB initialized successfully.")


def run_data_ingestion(app: FastAPI):
    """Runs all necessary data ingestion processes."""
    logger.info("Starting data ingestion processes...")
    LepTraits(app.state.duck_db).ingest()
    logger.info("LepTraits data ingested.")
    GbifPersistData(app.state.duck_db).ingest()
    logger.info("GBIF data ingested.")
    SpeciesImageUmap(app.state.duck_db).ingest()
    ImageMetaService(app.state.duck_db).ingest()

    image_embedder = ImageEmbedder(
        clip_model=app.state.clip_embedder.model,
        clip_processor=app.state.clip_embedder.processor,
        unicom_model=app.state.unicom_embedder.model,
        unicom_transform=app.state.unicom_embedder.transform,
        lance_db=app.state.lance_db,
    )
    image_embedder.ingest()
    logger.info("Image embeddings ingested.")
    logger.info(
        "All data ingestion processes completed successfully."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    This context manager handles the startup and shutdown logic for the FastAPI
    application. On startup, it initializes all necessary services like
    configuration, models, databases, and performs initial data ingestion.
    On shutdown, it will handle cleanup.
    """
    logger.info("Application starting up...")

    # Startup logic
    try:
        settings = get_app_settings()
        app.state.settings = settings
        logger.info("Application settings loaded and validated.")

        initialize_models(app)
        initialize_lance(app)
        initialize_duckdb(app)
        run_data_ingestion(app)

        logger.info("Application startup completed successfully.")
    except Exception as e:
        logger.critical(
            f"A critical error occurred during application startup: {e}"
        )
        raise

    # Yield control - application is now running
    yield

    # Shutdown logic (only runs if startup succeeded)
    logger.info("Application shutting down...")
    try:
        if (
            hasattr(app.state, "duckdb")
            and app.state.duck_db is not None
        ):
            app.state.duck_db.close()
        app.state.lance_db = None
        app.state.clip_embedder = None
        app.state.unicom_embedder = None
        logger.info("Application shutdown completed.")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


app = FastAPI(
    lifespan=lifespan,
    title="BIOCOSMOS API",
    version="0.1.0",
    description=description,
    summary="Butterfly diversity database with AI-powered search",
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/license/mit/",
    },
    openapi_tags=tags_metadata,
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ml_search.router)
app.include_router(data_stats.router)
app.include_router(species_data.router)
app.include_router(text_summarization.router)
app.include_router(image_retrieval.router)
app.include_router(db_search.router)
app.include_router(agent_search.router)


@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the CLIP Service"}


# Check server status okay
@app.get("/status", tags=["Server Health"])
async def status():
    logger.info("Status endpoint accessed")
    return {"status": "ok"}
