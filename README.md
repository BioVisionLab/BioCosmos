# BioCosmos - Biodiversity Image Platform

[![Backend-Tests](https://github.com/agporto/BioCosmos/workflows/Backend-Tests/badge.svg)](https://github.com/agporto/BioCosmos/actions)

A personalized, museum-quality biodiversity image platform that combines machine learning with intuitive web interfaces to explore and identify butterfly species. Built with Next.js, Python, and advanced computer vision technologies.

## Features

### Multi-Modal Search

- **Text Search**: Traditional species name search with autocomplete.
- **Semantic Search**: Natural language queries like "orange butterfly with black lines".
- **Visual Search**: Upload an image to find visually similar species.
- **Smart Search Toggle**: Seamlessly switch between search modes.

### Interactive Visualization

- **UMAP Map**: Explore species relationships through interactive similarity maps.
- **Zoomable Interface**: Navigate through different detail levels.
- **Image Overlays**: Species images positioned by visual similarity.
- **Tile-Based Rendering**: Optimized performance with map tiles.

### Taxonomic Navigation

- **Hierarchical Browsing**: Navigate from Class -> Order -> Family -> Genus -> Species.
- **Dynamic Routing**: Clean URLs for all taxonomic levels.
- **Breadcrumb Navigation**: Path tracking in the taxonomy tree.
- **Representative Images**: Visual previews for each taxonomic group.

### Rich Species Information

- **Detailed Profiles**: Scientific names, common names, biological descriptions, and conservation status.
- **Image Galleries**: High-quality images with lightbox viewing.
- **Geographic Maps**: Species distribution visualization using Leaflet and GBIF occurrence data.
- **Taxonomic Classification**: Complete hierarchical classification.

### AI Integration

- **CLIP Embeddings**: OpenAI's CLIP model for semantic understanding.
- **UNICOM**: Advanced computer vision model for visual similarity.
- **Agentic Search**: OpenAI function-calling search queries to intelligently query multiple data sources.

### Modern User Experience

- **Dark/Light Mode**: Automatic system preference detection with a manual toggle.
- **Responsive Layout**: Optimized for desktop, tablet, and mobile devices.
- **Loading States**: Smooth transitions and skeleton loading indicators.
- **Error Handling**: Graceful error recovery with user-friendly messages.

## Architecture

### Frontend Stack

- **Next.js**: React-based framework with App Router.
- **React**: Component-based user interface library.
- **TypeScript**: Type-safe development.
- **Tailwind CSS**: Utility-first styling with custom themes.
- **Leaflet.js & React Leaflet**: Interactive maps for geographic distribution.
- **Lucide React**: Clean, customizable iconography.

### Backend Stack

- **FastAPI**: Modern, high-performance web framework for APIs.
- **Python 3.10+**: Core backend language.
- **LanceDB**: Vector database for embedding storage and similarity search.
- **DuckDB**: In-process SQL OLAP database for structured metadata and taxonomy.
- **CLIP**: OpenAI's vision-language model for semantic search.
- **UNICOM**: Computer vision model optimized for fine-grained biological image similarity.
- **Polars**: High-performance DataFrame library for data processing.
- **Transformers**: Hugging Face library for ML model integration.
- **PyTorch**: Deep learning framework for model inference.

## Project Structure

```
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
│   ├── tests/                  # Backend tests
│   ├── Dockerfile              # Backend Dockerfile
│   └── pyproject.toml          # Python dependencies (managed by uv)
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
│   │   ├── SpeciesMap.tsx      # Leaflet geographic maps
│   │   └── ...                 # Other components
│   └── lib/                    # Helper functions and utilities
│       ├── backend.ts          # Backend status verification
│       ├── types.ts            # TypeScript types
│       └── ...                 # Other utilities
├── public/                   # Static assets
│   ├── images/                 # Species images (git-ignored)
│   ├── dataset-metadata/       # Metadata files
│   └── leaflet/                # Leaflet map assets
├── tools/                    # Data processing scripts
│   ├── clip_search_service.py  # CLI search using CLIP
│   ├── create_metadata_json.py # Process metadata
│   ├── create_tiles.py         # Generate map tiles for visualization
│   ├── embed_images.py         # Generate image embeddings
│   └── generate_tsne_coords.py # Create t-SNE visualization data
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

- **Yarn** (recommended), **Bun**, or **Node.js** (v18+)
- **Python** (v3.10 or higher)
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
    yarn install
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

    **Install backend dependencies:**

    ```bash
    cd backend
    uv sync
    cd ..
    ```

4. **Environment Configuration**

    **Frontend** - Create a `.env.local` file in the root directory:

    ```bash
    # Optional: OpenAI API key for agentic search
    OPENAI_API_KEY=your_openai_api_key_here
    
    # API host for local development
    API_HOST=http://127.0.0.1:8000
    ```

    **Backend** - Create a `.env` file in the `backend/` directory:

    ```bash
    DUCK_DIR=./duck_db
    LANCE_DIR=./lance_db_lite
    IMAGE_DIR=../public/images
    IMAGE_META_DIR=./data
    GBIF_DIR=./data
    UMAP_DIR=./data

    # Optional: Custom LLM service
    # LLM_API_URL=your_llm_endpoint
    # LLM_API_KEY=your_api_key
    ```

5. **Prepare the Dataset**

    Organize your butterfly images in the appropriate directory structure under `public/images/`.

6. **Generate Embeddings (First Time Setup)**

    ```bash
    cd backend
    
    # Generate image embeddings using CLIP and UNICOM
    uv run python ../tools/embed_images.py
    
    # Generate t-SNE visualization coordinates
    uv run python ../tools/generate_tsne_coords.py
    
    cd ..
    ```

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
    yarn dev
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

The `tools/` directory contains scripts for data processing:

- **embed_images.py**: Generate CLIP and UNICOM embeddings for images.
- **generate_tsne_coords.py**: Create t-SNE visualization coordinates.
- **create_metadata_json.py**: Process and format metadata.
- **create_tiles.py**: Generate map tiles for the UMAP/t-SNE visualization map.

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
yarn lint
```

## Development Tips

### Backend Development

- **Hot Reload**: Use `--reload` flag with uvicorn or run `fastapi dev` for auto-restart on code changes.
- **API Docs**: FastAPI automatically generates interactive API documentation at `/docs`.
- **Logging**: Configure logging levels in `backend/app/configs/config.yaml`.
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
  -e UMAP_DIR=/app/data \
  --env-file ./backend/.env \
  -v ./backend/duck_db:/app/duck_db:Z \
  -v ./backend/lance_db_lite:/app/lance_db:Z \
  -v ./backend/data:/app/data:Z \
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

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **OpenAI CLIP**: Vision-language model for semantic understanding
- **UNICOM**: Advanced computer vision model for biological images
- **LanceDB**: Fast vector database for similarity search
- **FastAPI**: Modern Python web framework
- **Next.js**: React framework with excellent developer experience
- **Leaflet**: Open-source mapping library
- **GBIF**: Global biodiversity data integration
- **Butterfly Dataset Contributors**: High-quality species images and data

---

**BioCosmos** - Exploring biodiversity through the lens of AI.
