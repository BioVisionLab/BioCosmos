import logging
import os
from contextlib import asynccontextmanager
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database.duckdb import DuckDBClient
from .services.unicom import UnicomModel
from .database.lance import LanceDB
from .services.clip import ClipModel
from .services.embedder import ImageEmbedder
from .services.umap import SpeciesImageUmap
from .services.metadata import ImageMetaService
from .services.gbif import GbifPersistData
from .configs.config import (
    ColConfig,
    GbifConfig,
    ImageConfig,
    LocalityConfig,
    ProvenanceConfig,
)
from .services.col import ColBackboneService
from .services.locality import LocalityService
from .services.provenance import ProvenanceService
from .services.taxonomy_update import TaxonomyUpdateService
from .services.leptraits import LepTraits
from .routers import (
    data_stats,
    image_retrieval,
    ml_search,
    species_data,
    text_summarization,
    db_search,
    agent_search,
    taxonomy,
    geography,
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
    IMAGE_META_DIR: str
    GBIF_DIR: str
    UMAP_DIR: str
    # Optional on purpose. A deployment without the Catalogue of Life release
    # still serves everything but the classification panel, so a missing
    # COL_DIR must not stop the service booting. run_data_ingestion logs what
    # is missing instead.
    COL_DIR: Optional[str] = None
    LLM_API_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None

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
        missing_vars = [err["loc"][0] for err in e.errors() if "loc" in err]
        error_message = f"Missing or invalid required environment variables: {', '.join(missing_vars)}"
        logger.error(error_message)
        raise EnvironmentError(error_message) from e


def initialize_models(app: FastAPI):
    """Initializes and attaches machine learning models to the app state."""
    logger.info("Initializing CLIP model...")
    clip_model, clip_processor = ClipModel.load_model()
    app.state.clip_embedder = ClipModel(model=clip_model, processor=clip_processor)
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


def report_taxonomy_readiness(duck_db) -> None:
    """Say at startup whether taxonomy is available, and why it is not.

    Without this the only signal is a catalog error per search, which says
    nothing about the cause. Both tables are optional: the site still serves
    images, traits and specimens without either.
    """
    col_config = ColConfig()
    if not duck_db.table_exists(col_config.table):
        if col_config.skip:
            reason = "col.skip is true in backend/app/configs/config.yaml"
        elif not os.path.isfile(col_config.path):
            reason = f"no Catalogue of Life release at {col_config.path}"
        else:
            # The release is there, so the ingest itself failed; its own error
            # was logged when it did.
            reason = "the ingest did not complete, see the errors above"
        logger.warning(
            f"No taxonomy backbone: {reason}. Species pages will render "
            "without a classification. Set COL_DIR to an extracted ColDP "
            "release and restart to build it."
        )
    else:
        logger.info("CoL taxonomy backbone ready.")

    if not duck_db.table_exists(col_config.occurrence_status_table):
        logger.warning(
            "No taxonomic update, so specimens carry no match status. It is "
            "built from the same release as the backbone, so the cause is the "
            "one reported above."
        )
    else:
        logger.info("Taxonomic update ready.")


def report_locality_readiness(duck_db) -> None:
    """Say at startup whether locality and coordinate validation are available.

    Both are optional joins, so the only other signal is a silently empty
    column. The coordinate table is never built here -- it comes from a CLI run
    -- so the message names the command rather than a configuration key.
    """
    config = LocalityConfig()
    if not duck_db.table_exists(config.table):
        if config.skip:
            reason = "locality.skip is true in backend/app/configs/config.yaml"
        elif not duck_db.table_exists(GbifConfig().table):
            reason = (
                "there is no gbif_meta table, which is where the locality fields live"
            )
        else:
            # The inputs are there, so the build itself failed; its own error
            # was logged when it did.
            reason = "the build did not complete, see the errors above"
        logger.warning(
            f"No occurrence locality: {reason}. Specimens will render without "
            "a country or locality."
        )
    else:
        logger.info("Occurrence locality ready.")

    if not duck_db.table_exists(config.coordinates_table):
        logger.warning(
            "No coordinate validation, so specimens carry no coordinate status. "
            "It is written by `geoharmonize integrate`, which has to be run once "
            "with this process stopped; see packages/geoharmonize/README.md."
        )
    else:
        logger.info("Coordinate validation ready.")


def report_provenance_readiness(duck_db) -> None:
    """Say at startup whether the per-occurrence provenance join is available."""
    config = ProvenanceConfig()
    if not duck_db.table_exists(config.table):
        if config.skip:
            reason = "provenance.skip is true in backend/app/configs/config.yaml"
        elif not duck_db.table_exists(GbifConfig().table):
            reason = (
                "there is no gbif_meta table, which is where the institution "
                "and catalog fields live"
            )
        else:
            reason = "the build did not complete, see the errors above"
        logger.warning(
            f"No occurrence provenance: {reason}. Specimens will render "
            "without an institution or specimen ID."
        )
    else:
        logger.info("Occurrence provenance ready.")


def run_data_ingestion(app: FastAPI):
    """Runs all necessary data ingestion processes."""
    logger.info("Starting data ingestion processes...")
    LepTraits(app.state.duck_db).ingest()
    logger.info("LepTraits data ingested.")
    GbifPersistData(app.state.duck_db).ingest()
    logger.info("GBIF data ingested.")
    SpeciesImageUmap(app.state.duck_db).ingest()
    ImageMetaService(app.state.duck_db).ingest()

    # CoL supplies the taxonomy backbone, and the colharmonize run resolves
    # each occurrence against it. Both run after image_meta, which the
    # per-occurrence status table is built from.
    ColBackboneService(app.state.duck_db).ingest()
    TaxonomyUpdateService(app.state.duck_db).ensure()
    report_taxonomy_readiness(app.state.duck_db)

    # Locality is derived from gbif_meta rather than from image_meta, which
    # carries no locality columns of its own, so it runs after both.
    LocalityService(app.state.duck_db).ensure()
    report_locality_readiness(app.state.duck_db)

    # Institution and specimen identifier, from the same gbif_meta join.
    ProvenanceService(app.state.duck_db).ensure()
    report_provenance_readiness(app.state.duck_db)

    image_embedder = ImageEmbedder(
        clip_model=app.state.clip_embedder.model,
        clip_processor=app.state.clip_embedder.processor,
        unicom_model=app.state.unicom_embedder.model,
        unicom_transform=app.state.unicom_embedder.transform,
        lance_db=app.state.lance_db,
    )
    image_embedder.ingest()
    logger.info("Image embeddings ingested.")

    rebuild_search_indexes(app)

    logger.info("All data ingestion processes completed successfully.")


def rebuild_search_indexes(app: FastAPI):
    """Refresh every search index so it describes the data as it is now.

    Two different kinds of index, with two different policies:

    * The DuckDB full-text indexes are rebuilt on **every** start. Ingestion is
      normally skipped in production, so without this the index is whatever the
      last ingest left behind -- and the database changes underneath it through
      routes that never touch ingestion, such as a `geoharmonize integrate` run
      or a colharmonize update. Rebuilding is cheap next to serving stale hits.

    * The LanceDB vector indexes are built **once** and then left alone.
      Training an IVF-PQ index is minutes of work and only becomes stale when
      the embeddings themselves change, which a restart does not do.

    Neither is allowed to fail startup: an index that is missing or stale makes
    search slower or slightly out of date, and neither is worth taking the site
    down for.
    """
    logger.info("Refreshing search indexes...")

    if ImageMetaService(app.state.duck_db).reindex():
        logger.info("Image metadata full-text index rebuilt.")
    if GbifPersistData(app.state.duck_db).reindex():
        logger.info("GBIF full-text index rebuilt.")

    image_config = ImageConfig()
    for column in ("unicom_embeddings", "clip_embeddings"):
        app.state.lance_db.ensure_vector_index(image_config.table, column)

    logger.info("Search indexes refreshed.")


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
        logger.critical(f"A critical error occurred during application startup: {e}")
        raise

    # Yield control - application is now running
    yield

    # Shutdown logic (only runs if startup succeeded)
    logger.info("Application shutting down...")
    try:
        if hasattr(app.state, "duck_db") and app.state.duck_db is not None:
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
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://biocosmos.rc.ufl.edu",
        "https://biocosmos.rc.ufl.edu",
        "http://biocosmos-admin.rc.ufl.edu",
        "https://biocosmos-admin.rc.ufl.edu",
        "https://lepiverse.com",
        "https://www.lepiverse.com",
    ],
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
app.include_router(taxonomy.router)
app.include_router(geography.router)


@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the CLIP Service"}


# Check server status okay
@app.get("/status", tags=["Server Health"])
async def status():
    logger.info("Status endpoint accessed")
    return {"status": "ok"}
