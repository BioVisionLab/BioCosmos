# Contributing to BioCosmos

First off, thank you for considering contributing to BioCosmos! It's people like you that make open source such a great community. We welcome any and all contributions.

## Code of Conduct

This project and everyone participating in it is governed by the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## How Can I Contribute?

There are many ways to contribute to BioCosmos, from writing code and documentation to reporting bugs and suggesting new features.

- **Reporting Bugs:** If you find a bug, please open an issue on our GitHub issue tracker.
- **Suggesting Enhancements:** If you have an idea for a new feature, open an issue to discuss it.
- **Pull Requests:** We welcome pull requests! Please follow the steps below.

## Pull Request Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Project Structure

```text
biocosmos/
├── backend/                  # Python backend (FastAPI)
│   ├── duck_db/                # DuckDB database files (git-ignored)
│   ├── lance_db_lite/          # LanceDB vector database files (git-ignored)
│   ├── data/                   # Metadata files: parquet, CSV, TSV (git-ignored)
│   ├── static/                 # Processed images, thumbnails, tiles (git-ignored)
│   ├── app/                    # Core application code
│   │   ├── main.py             # FastAPI entrypoint
│   │   ├── configs/            # Configuration files and settings
│   │   ├── database/           # Database models and connections
│   │   │   ├── duckdb.py       # DuckDB operations
│   │   │   ├── lance.py        # LanceDB operations
│   │   │   └── model.py        # Data models
│   │   ├── query/              # Database query logic
│   │   │   ├── agent_query.py          # Agent query parsing
│   │   │   ├── db_search.py            # DuckDB SQL text search
│   │   │   ├── image_files.py          # Image path retrieval
│   │   │   ├── image_search.py         # Vector database searches
│   │   │   ├── precomputed_similarity.py # Precomputed visual similarity
│   │   │   ├── species_similarity.py   # Runtime visual similarity
│   │   │   ├── specimen_data.py        # Specimen and UMAP queries
│   │   │   └── taxon_data.py           # Taxonomic query service
│   │   ├── routers/            # API endpoints
│   │   │   ├── agent_search.py # Agentic search endpoints
│   │   │   ├── data_stats.py   # Statistics endpoints
│   │   │   ├── db_search.py    # Database search endpoints
│   │   │   ├── image_retrieval.py  # Image serving endpoints
│   │   │   ├── ml_search.py    # ML-based search endpoints
│   │   │   ├── species_data.py # Species data endpoints
│   │   │   └── text_summarization.py  # AI summarization endpoints
│   │   └── services/           # Business logic and ML services
│   │       ├── agent.py        # Agentic search and automation logic
│   │       ├── clip.py         # CLIP model integration
│   │       ├── embedder.py     # Embedder base classes and operations
│   │       ├── gbif.py         # GBIF API integration
│   │       ├── images.py       # Image processing and management
│   │       ├── leptraits.py    # Trait data processing
│   │       ├── metadata.py     # Metadata ingestion/query services
│   │       ├── openai.py       # OpenAI API integration
│   │       ├── umap.py         # UMAP dimensionality reduction
│   │       └── unicom.py       # UNICOM model integration
│   ├── scripts/                # Maintained backend data-processing scripts
│   │   └── precompute_similarity.py # Precompute species similarity in DuckDB
│   ├── tests/                  # Backend tests
│   ├── Dockerfile              # Backend Dockerfile
│   └── pyproject.toml          # Backend dependencies (uv workspace member)
├── packages/                 # Offline data-harmonization tools (uv workspace members)
│   ├── harmonize-core/         # Shared DuckDB, config, output, reporting primitives
│   ├── colharmonize/           # Catalogue of Life taxonomy matching CLI
│   └── geoharmonize/           # GADM coordinate validation CLI
├── reports/                  # Generated run artifacts and manifests (git-ignored)
├── pyproject.toml            # uv workspace root
├── uv.lock                   # Single lockfile for backend and packages
├── src/                      # Next.js frontend
│   ├── app/                    # App Router pages and layouts
│   │   ├── page.tsx            # Home page
│   │   ├── layout.tsx          # Root layout
│   │   ├── about/              # About page
│   │   ├── api/                # API proxy route handlers
│   │   ├── collections/        # Collections pages
│   │   ├── family/             # Family taxonomy pages
│   │   ├── genus/              # Genus taxonomy pages
│   │   ├── resources/          # Resources page
│   │   ├── search/             # Search results page
│   │   ├── species/            # Species detail pages
│   │   └── visualization/      # t-SNE visualization page
│   ├── components/             # React components
│   │   ├── ui/                 # UI components (buttons, dialogs, etc.)
│   │   ├── Attribution.tsx     # Data attribution
│   │   ├── HomePage.tsx        # Homepage content
│   │   ├── ImageSearch.tsx     # Image search interface
│   │   ├── SearchBar.tsx       # Navigation search bar
│   │   ├── SpeciesMap.tsx      # MapLibre geographic maps
│   │   └── ...                 # Other components
│   └── lib/                    # Helper functions and utilities
│       ├── backend.ts          # Backend status verification
│       ├── types.ts            # TypeScript types
│       └── ...                 # Other utilities
├── public/                   # Static assets
│   ├── images/                 # Species images (git-ignored)
│   ├── dataset-metadata/       # Metadata files
├── tools/                    # Outdated, unused code; not part of data preparation
├── scripts/                  # Convenience runner scripts
│   ├── run_backend.sh          # Start backend (Linux/macOS)
│   ├── run_backend_prod.sh     # Start backend in production mode (Linux/macOS)
│   ├── run_backend.ps1         # Start backend (Windows)
│   ├── run_frontend.sh         # Start frontend (Linux/macOS)
│   └── run_frontend.ps1        # Start frontend (Windows)
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile.frontend       # Frontend Dockerfile
├── package.json              # Frontend dependencies
├── tsconfig.json             # TypeScript configuration
└── tailwind.config.ts        # Tailwind CSS configuration
```

## Local Development Setup

### Prerequisites

- **Bun** (recommended), **Yarn**,  or **Node.js** (v18+)
- **Python** (v3.12 or higher)
- **uv** - Modern Python package manager (recommended)
- **Git**
- **Docker** and **Docker Compose** (optional, for containerized deployment)
- **OpenAI API Key** (optional, for agentic search functionality)

### Manual Setup (Development)

If you prefer to run the services manually without Docker, follow these steps:

1. **Clone the Repository**

    ```bash
    git clone <repository-url>
    cd biocosmos
    ```

2. **Install Frontend Dependencies**

    ```bash
    bun install
    ```

3. **Set Up Python Environment**

    We use [uv](https://docs.astral.sh/uv/) for fast, reliable Python dependency management:

    **Install uv:**

    ```bash
    # On macOS/Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Or via pip
    pip install uv
    ```

    **Install the Python workspace dependencies from the repository root:**

    ```bash
    uv sync --all-packages
    ```

4. **Environment Configuration**

    **Frontend** - Create a `.env.local` file in the root directory:

    ```bash
    API_HOST=http://127.0.0.1:8000
    ```

    **Backend** - Create `backend/.env`. Use absolute paths: the backend helper
    runs from `backend/`, while the harmonization CLIs run from the repository
    root, so relative paths otherwise refer to different directories.

    ```bash
    DUCK_DIR=/absolute/path/to/BioCosmos/backend/duck_db
    LANCE_DIR=/absolute/path/to/BioCosmos/backend/lance_db_lite
    IMAGE_DIR=/absolute/path/to/BioCosmos/public/images
    IMAGE_META_DIR=/absolute/path/to/BioCosmos/backend/data
    GBIF_DIR=/absolute/path/to/BioCosmos/backend/data
    UMAP_DIR=/absolute/path/to/BioCosmos/backend/data

    # Optional, but required for Catalogue of Life ingestion and matching.
    # This directory must contain an extracted ColDP NameUsage.tsv.
    COL_DIR=/absolute/path/to/catalogue-of-life-col-dp

    # Optional: Custom LLM service
    # LLM_API_URL=your_llm_endpoint
    # LLM_API_KEY=your_api_key
    ```

    `DUCK_DIR` is a directory; the backend opens
    `$DUCK_DIR/biocosmos.duckdb`. `COL_DIR` is also a directory, not the path
    to `NameUsage.tsv` itself. Keep `.env` files and credentials out of Git.

    The offline geography workflow also needs a directory containing
    `gadm_410-levels.gpkg`. `GADM_DIR` is a shell variable used by the commands
    below, not a backend setting. From the repository root, load
    `backend/.env` into the current shell and set the GADM path:

    ```bash
    set -a
    source backend/.env
    set +a
    export GADM_DIR=/absolute/path/to/gadm
    ```

5. **Prepare the Dataset**

    Organize your butterfly images in the appropriate directory structure under `public/images/`.

6. **Prepare Data with the Maintained Tools**

    Follow [Data Preparation](#data-preparation) for `colharmonize`, `geoharmonize`, and the scripts under `backend/scripts/`. The root `tools/` directory is outdated and unused.

7. **Start the Services**

    **Option A - Using convenience scripts:**

    ```bash
    # Terminal 1 - Backend
    ./scripts/run_backend.sh

    # Terminal 2 - Frontend
    ./scripts/run_frontend.sh
    ```

    **Option B - Manual commands:**

    **Terminal 1 - Backend:**

    ```bash
    cd backend
    uv run --env-file .env -- fastapi dev
    # Or: uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```

    **Terminal 2 - Frontend:**

    ```bash
    bun dev
    ```

8. **Access the Application**

    - **Frontend**: [http://localhost:3000](http://localhost:3000)
    - **Backend API**: [http://localhost:8000](http://localhost:8000)
    - **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

## Data Management

### Database Structure

BioCosmos uses two complementary databases:

1. **LanceDB** (Vector Database)
   - Stores image embeddings for similarity search.
   - Supports both CLIP and UNICOM embeddings.
   - Enables fast nearest-neighbor queries.

2. **DuckDB** (Analytical Database)
   - Stores species metadata and taxonomic information.
   - Handles structured queries and aggregations.
   - Provides trait and geographic data.

### Data Preparation

Data preparation uses the harmonization packages and maintained backend scripts:

- **colharmonize** (`packages/colharmonize/`): Match occurrence species names against a Catalogue of Life release.
- **geoharmonize** (`packages/geoharmonize/`): Validate occurrence coordinates against GADM geography. `geoharmonize integrate` writes the coordinate-validation table read by the backend.
- **Backend scripts** (`backend/scripts/`): `precompute_similarity.py` computes per-species visual similarity from existing LanceDB embeddings and DuckDB metadata, then stores the results in DuckDB.

Sync all packages first:

```bash
uv sync --all-packages
```

Run every command in this section from the repository root. The examples assume
the absolute path variables from [Environment Configuration](#environment-configuration)
are exported in the current shell. The required reference inputs are:

- An extracted Catalogue of Life ColDP release at `$COL_DIR`, including
  `$COL_DIR/NameUsage.tsv`.
- The GADM 4.1 GeoPackage at `$GADM_DIR/gadm_410-levels.gpkg`.

Inspect the CLI options and the source table before running taxonomy matching:

```bash
uv run colharmonize --help
uv run geoharmonize --help

uv run colharmonize inspect --db "$DUCK_DIR/biocosmos.duckdb" \
  --table main.image_meta --map scientific_name=species \
  --map family=family --map order=order --map class=class --map kingdom=kingdom
```

The backend performs the same taxonomy harmonization during startup, so this
CLI run is optional for the site. Use it when tuning matching or exporting the
CSV summary and plot:

```bash
uv run colharmonize run --db "$DUCK_DIR/biocosmos.duckdb" \
  --table main.image_meta --map scientific_name=species \
  --map family=family --map order=order --map class=class --map kingdom=kingdom \
  --col "$COL_DIR/NameUsage.tsv" --reports-dir reports --csv --plot
```

Geography has one additional prerequisite. The backend must run once after the
current `image_meta` and `gbif_meta` tables are loaded so `LocalityService` can
join them into `main.image_meta_locality`. Start it and wait for either
`Locality table built` or `Occurrence locality ready` in the log, then stop it
with Ctrl-C so the offline writer can open DuckDB:

```bash
./scripts/run_backend.sh
```

Confirm the derived table and its resolved coordinate fields:

```bash
uv run geoharmonize inspect --db "$DUCK_DIR/biocosmos.duckdb" \
  --list-columns main.image_meta_locality

uv run geoharmonize inspect --db "$DUCK_DIR/biocosmos.duckdb" \
  --table main.image_meta_locality \
  --map source_id=img_id --map country=country_code --map adm1=state_province
```

Then validate the coordinates and write the table consumed by the backend:

```bash
uv run geoharmonize integrate --db "$DUCK_DIR/biocosmos.duckdb" \
  --table main.image_meta_locality --gadm "$GADM_DIR/gadm_410-levels.gpkg" \
  --map source_id=img_id --map country=country_code --map adm1=state_province \
  --into main.image_meta_coordinates --reports-dir reports
```

Do not substitute `main.image_meta` in that command: it contains `img_id`,
`lat`, and `lon`, but its `country_code` and `state_province` values live in
`gbif_meta` until the backend constructs `image_meta_locality`. If
`main.image_meta_coordinates` already exists, review it and add `--replace` to
the integration command to rebuild it.

Stop the backend before either CLI accesses the live database. DuckDB permits
only one writer, and the API keeps the file open read-write while it runs.

To precompute similarity with existing embeddings and metadata:

```bash
cd backend
uv run python scripts/precompute_similarity.py --lance-dir lance_db_lite --duck-dir duck_db
```

After rebuilding embeddings, set `search_index.build_vector: true` in
`backend/app/configs/config.yaml` for the next backend start so the LanceDB
IVF-PQ indexes are retrained against them, then set it back to `false`.

See [packages/README.md](packages/README.md) and [reports/README.md](reports/README.md)
for the package details and generated artifact contract.

Everything in the root `tools/` directory is outdated and unused. Do not use those scripts for data preparation, embedding generation, or visualization setup.

## Testing

### Backend Tests

Run pytest in the backend directory:

```bash
cd backend
uv run pytest
```

### Frontend Linting

Run ESLint to check for frontend issues:

```bash
bun lint
```

## Development Tips

### Backend Development

- **Hot Reload**: Use `--reload` flag with uvicorn or run `fastapi dev` for auto-restart on code changes.
- **API Docs**: FastAPI automatically generates interactive API documentation at `/docs`.
- **Logging**: Configure logging levels in `backend/app/configs/config.yaml`.
- **Search index**: `search_index.build_vector` in `backend/app/configs/config.yaml` is `false`, so an ordinary start builds no vector index and similarity search falls back to a brute-force cosine scan. Set it `true` for one boot after the embeddings are rebuilt, then back to `false` — training the index is minutes of work that a restart does not invalidate. Startup logs which path it took.
- **Dependencies**: Add new packages with `uv add <package>`.
- **Environment Variables**: Backend reads from `backend/.env` file for configuration.
- **Convenience Scripts**: Use `scripts/run_backend.sh` for quick startup.

### Frontend Development

- **TypeScript**: All components use TypeScript for type safety.
- **Tailwind CSS**: Utility-first styling with custom theme configuration.
- **Dark Mode**: Theme handled by `next-themes` with system preference detection.
- **API Integration**: Next.js route handlers in `src/app/api/` proxy requests to the backend.
- **Convenience Scripts**: Use `scripts/run_frontend.sh` for quick startup.

## Deployment

### Docker Deployment

The project includes Docker configurations for easy deployment:

```bash
# Build and run with Docker Compose
docker-compose up --build

# Run in detached mode
docker-compose up -d

# Stop services
docker-compose down
```

### Podman / Docker (Manual Container Runs)

If you don't have `docker-compose`, you can run the containers manually:

**Step 1: Create a shared network**

```bash
docker network create biocosmos
```

**Step 2: Build the images**

```bash
# From project root
docker build -t biocosmos-backend ./backend
docker build -t biocosmos-frontend -f Dockerfile.frontend .
```

**Step 3: Run the backend**

```bash
docker run -d \
  --name backend \
  --network biocosmos \
  -p 8000:80 \
  -e DUCK_DIR=/app/duck_db \
  -e LANCE_DIR=/app/lance_db \
  -e IMAGE_DIR=/app/images \
  -e IMAGE_META_DIR=/app/data \
  -e GBIF_DIR=/app/data \
  -e COL_DIR=/app/data/col \
  -e UMAP_DIR=/app/data \
  --env-file ./backend/.env \
  -v ./backend/duck_db:/app/duck_db:Z \
  -v ./backend/lance_db_lite:/app/lance_db:Z \
  -v ./backend/data:/app/data:Z \
  -v /absolute/path/to/catalogue-of-life-col-dp:/app/data/col:ro \
  -v ./backend/static:/app/static:Z \
  -v ./public/images:/app/images:Z \
  biocosmos-backend
```

**Step 4: Run the frontend**

```bash
docker run -d \
  --name frontend \
  --network biocosmos \
  -p 3000:3000 \
  -e API_HOST=http://backend:80 \
  biocosmos-frontend
```

## API Endpoints

### Frontend proxy API endpoints (Next.js API route handlers)

- `GET /api/status` - Checks the backend status.
- `GET /api/db-search` - Conventional database search. Query parameters: `q` (search term), `field` (column to search, e.g., `"all"`), `page` (page number).
- `GET /api/gbif-occurrences` - Retrieves species occurrence data from the public GBIF API. Query parameters: `species`.
- `GET /api/images/id` - Fetches species image by ID. Query parameters: `imageId`.
- `GET /api/images/id/metadata` - Fetches metadata for an image ID. Query parameters: `imageId`.
- `GET /api/images/metadata` - Retrieves all image IDs for a species. Query parameters: `scientificName`.
- `GET /api/images/species` - Fetches representative species image. Query parameters: `scientificName`, `type` (`"thumbnail"` or `"full"`).
- `GET /api/ml-search/agent` - Agentic semantic search. Query parameters: `q`.
- `POST /api/ml-search/image` - Image-to-image similarity search. Expects file upload (`file`).
- `GET /api/ml-search/similarity` - Fetches visually similar species. Query parameters: `species`.
- `GET /api/ml-search/text` - Text-based semantic image search. Query parameters: `q`.
- `GET /api/specimens` - Fetches specimens for a species. Query parameters: `species`.
- `GET /api/stats/umap` - Fetches UMAP coordinates for a species. Query parameters: `species`.
- `GET /api/taxon-search` - Fetches biological taxonomy and trait data for a species. Query parameters: `species`.

### Backend API endpoints (Python FastAPI)

- `GET /status` - Server health status check.
- `GET /search/text` - Text-based semantic search. Query parameters: `q` (search query), `limit` (max results, default 50).
- `POST /search/image` - Image-based similarity search. Expects multipart file upload (`file`).
- `GET /search/db` - Conventional database search. Query parameters: `q` (search term), `field` (specific field or `"all"`), `page` (default 1), `limit` (default 50).
- `GET /search/agent` - Agentic multi-modal search. Query parameters: `q`.
- `GET /species/{scientific_name}/biology` - Detailed biological profile, taxonomic classification, traits, and similar species.
- `GET /species/{scientific_name}/similar` - Visually similar species (precomputed or runtime fallback).
- `GET /species/{scientific_name}/specimens` - Specimen details and images.
- `GET /family/{family_name}/classification` - GBIF classification data for a family.
- `GET /genus/{genus_name}/classification` - GBIF classification data for a genus.
- `GET /species/{genus}/{specific_epithet}/classification` - GBIF classification data for a species using genus and specific epithet.
- `GET /image/id/{image_id}` - Get full-resolution species image by image ID.
- `GET /image/id/{image_id}/metadata` - Fetch metadata for a single image ID.
- `GET /image/id/{image_id}/thumbnail` - Fetch thumbnail image for a single image ID.
- `GET /image/{scientific_name}/metadata` - Get all image IDs associated with a species.
- `GET /image/{scientific_name}/thumbnail` - Get representative thumbnail for a species.
- `GET /image/{scientific_name}/high-resolution` - Get representative high-resolution image for a species.
- `GET /stats/taxon` - Taxonomic statistics (counts of species in each taxon).
- `GET /stats/umap/{species}` - UMAP statistics/embeddings for a given species.
- `GET /summarize/{species_name}` - AI text summarization and profile generation for a species.

For complete backend API documentation, visit [http://localhost:8000/docs](http://localhost:8000/docs) when running the backend locally.

## Coding Standards

### Frontend

- We use [ESLint](https://eslint.org/) for linting. Please run `bun lint` before committing.
- Code is formatted automatically on commit using pre-commit hooks.

### Backend

- We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting.
- Please run `ruff check .` and `ruff format .` in the `backend` directory before committing.

We look forward to your contributions!
