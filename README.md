# 🦋 BioCosmos - Biodiversity Image Platform

![Backend-Tests](https://github.com/agporto/BioCosmos/workflows/Backend-Tests/badge.svg)

A personalized, museum-quality biodiversity image platform that combines cutting-edge machine learning with intuitive web interfaces to explore and identify butterfly species. Built with Next.js, Python, and advanced computer vision technologies.

## 🌟 Features

### 🔍 Multi-Modal Search

- **Text Search**: Traditional species name search with autocomplete
- **Semantic Search**: Natural language queries like "orange butterfly with black lines"
- **Visual Search**: Upload an image to find visually similar species
- **Smart Search Toggle**: Seamlessly switch between search modes

### 🗺️ Interactive Visualization

- **t-SNE Map**: Explore species relationships through interactive similarity maps
- **Zoomable Interface**: Navigate through different detail levels
- **Image Overlays**: Species images positioned by visual similarity
- **Tile-Based Rendering**: Optimized performance with map tiles

### 🏛️ Taxonomic Navigation

- **Hierarchical Browsing**: Navigate from Class → Order → Family → Genus → Species
- **Dynamic Routing**: Clean URLs for all taxonomic levels
- **Breadcrumb Navigation**: Always know where you are in the taxonomy
- **Representative Images**: Visual previews for each taxonomic group

### 🦋 Rich Species Information

- **Detailed Profiles**: Scientific names, common names, descriptions, conservation status
- **Image Galleries**: High-quality images with lightbox viewing
- **Geographic Maps**: Species distribution visualization
- **Taxonomic Classification**: Complete hierarchical classification

### 🤖 AI Integration

- **Intelligent Chatbot**: Ask questions about biodiversity, taxonomy, and conservation
- **CLIP Embeddings**: Advanced computer vision for semantic understanding
- **Natural Language Processing**: Powered by OpenAI's language models

### 🎨 Modern User Experience

- **Dark/Light Mode**: Automatic system preference detection with manual toggle
- **Responsive Design**: Optimized for desktop, tablet, and mobile
- **Loading States**: Smooth transitions and progress indicators
- **Error Handling**: Graceful error recovery with user-friendly messages

## 🏗️ Architecture

### Frontend Stack

- **Next.js**: React-based framework with App Router
- **React**: For building user interfaces
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling with custom theming
- **Leaflet.js**: Interactive maps for visualization
- **Lucide React**: Beautiful, customizable icons

### Backend Stack

- **FastAPI**: Modern, high-performance web framework for building APIs
- **Python 3.10+**: Core backend language
- **LanceDB**: Vector database for embedding storage and similarity search
- **DuckDB**: In-process SQL OLAP database for structured data
- **CLIP**: OpenAI's vision-language model for semantic search
- **UNICOM**: Advanced computer vision model for visual similarity
- **Polars**: High-performance DataFrame library for data processing
- **ChromaDB**: Vector database for additional embedding operations
- **Transformers**: Hugging Face library for ML model integration
- **PyTorch**: Deep learning framework for model inference

## 📁 Project Structure

```bash
biocosmos/
├── backend/                  # Python backend (FastAPI)
│   ├── app/                    # Core application code
│   │   ├── main.py             # FastAPI entrypoint
│   │   ├── configs/            # Configuration files and settings
│   │   ├── database/           # Database models and connections
│   │   │   ├── duckdb.py       # DuckDB operations
│   │   │   ├── lance.py        # LanceDB operations
│   │   │   └── model.py        # Data models
│   │   ├── query/              # Database query logic
│   │   ├── routers/            # API endpoints
│   │   │   ├── data_stats.py   # Statistics endpoints
│   │   │   ├── db_search.py    # Database search endpoints
│   │   │   ├── image_retrieval.py  # Image serving endpoints
│   │   │   ├── ml_search.py    # ML-based search endpoints
│   │   │   ├── species_data.py # Species data endpoints
│   │   │   └── text_summarization.py  # AI chatbot endpoints
│   │   └── services/           # Business logic and ML services
│   │       ├── clip.py         # CLIP model integration
│   │       ├── unicom.py       # UNICOM model integration
│   │       ├── images.py       # Image processing and embedding
│   │       ├── gbif.py         # GBIF API integration
│   │       ├── leptraits.py    # Trait data processing
│   │       └── openai.py       # OpenAI API integration
│   ├── tests/                  # Backend tests
│   ├── Dockerfile              # Backend Dockerfile
│   └── pyproject.toml          # Python dependencies (uv)
├── src/                      # Next.js frontend
│   ├── app/                    # App Router pages and layouts
│   │   ├── page.tsx            # Home page
│   │   ├── layout.tsx          # Root layout
│   │   ├── about/              # About page
│   │   ├── api/                # API route handlers
│   │   ├── collections/        # Collections pages
│   │   ├── family/             # Family taxonomy pages
│   │   ├── genus/              # Genus taxonomy pages
│   │   ├── resources/          # Resources page
│   │   ├── search/             # Search results page
│   │   ├── species/            # Species detail pages
│   │   └── visualization/      # t-SNE visualization page
│   ├── components/             # React components
│   │   ├── ui/                 # UI components
│   │   ├── ChatbotPanel.tsx    # AI chatbot
│   │   ├── ImageSearch.tsx     # Image search component
│   │   ├── SearchBar.tsx       # Search interface
│   │   ├── SpeciesMap.tsx      # Geographic maps
│   │   └── ...                 # Other components
│   └── lib/                    # Helper functions and utilities
│       ├── backend.ts          # Backend API client
│       ├── types.ts            # TypeScript types
│       └── ...                 # Other utilities
├── public/                   # Static assets
│   ├── images/                 # Species images
│   ├── dataset-metadata/       # Metadata files
│   └── leaflet/                # Leaflet map assets
├── tools/                    # Data processing scripts
│   ├── embed_images.py         # Generate image embeddings
│   ├── generate_tsne_coords.py # Create t-SNE visualization data
│   └── create_metadata_json.py # Process metadata
├── scripts/                  # Convenience runner scripts
│   ├── run_backend.sh          # Start backend (Linux/macOS)
│   ├── run_backend.ps1         # Start backend (Windows)
│   ├── run_frontend.sh         # Start frontend (Linux/macOS)
│   └── run_frontend.ps1        # Start frontend (Windows)
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile.frontend       # Frontend Dockerfile
├── package.json              # Frontend dependencies (Yarn)
├── tsconfig.json             # TypeScript configuration
└── tailwind.config.ts        # Tailwind CSS configuration
```

## 🚀 Local Development Setup

### Prerequisites

- **Node.js** (v18 or higher) and **Yarn** package manager
- **Python** (v3.10 or higher)
- **uv** - Modern Python package manager (recommended)
- **Git**
- **Docker** and **Docker Compose** (for containerized deployment)
- **OpenAI API Key** (optional, for chatbot functionality)

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
    # Optional: OpenAI API key for chatbot functionality
    OPENAI_API_KEY=your_openai_api_key_here
    
    # API host for local development
    API_HOST=http://127.0.0.1:8000
    ```

    **Backend** - Create a `.env` file in the `backend/` directory:

    ```bash
    # Optional: Database directory paths (defaults to current directory if not set)
    DUCK_DIR=./duck_db
    LANCE_DIR=./lance_db
    GBIF_DIR=./data
    IMAGE_DIR=../public/images
    
    # Optional: Custom AI service (UF AI or similar)
    # UF_AI_URL=your_ai_service_url
    # UF_AI_API_KEY=your_ai_api_key
    ```

5. **Prepare the Dataset**

    Organize your butterfly images in the appropriate directory structure. See the data preparation section for details.

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

    **Option B - Manual commands:**`

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

## 🗄️ Data Management

### Database Structure

BioCosmos uses two complementary databases:

1. **LanceDB** (Vector Database)
   - Stores image embeddings for similarity search
   - Supports both CLIP and UNICOM embeddings
   - Enables fast nearest-neighbor queries

2. **DuckDB** (Analytical Database)
   - Stores species metadata and taxonomic information
   - Handles structured queries and aggregations
   - Provides trait and geographic data

### Data Preparation

The `tools/` directory contains scripts for data processing:

- **embed_images.py**: Generate CLIP and UNICOM embeddings for images
- **generate_tsne_coords.py**: Create t-SNE visualization coordinates
- **create_metadata_json.py**: Process and format metadata

## 🧪 Testing

### Backend Tests

```bash
cd backend
uv run pytest
```

### Frontend Linting

```bash
yarn lint
```

## 🛠️ Development Tips

### Backend Development

- **Hot Reload**: Use `--reload` flag with uvicorn for auto-restart on code changes
- **API Docs**: FastAPI automatically generates interactive API documentation at `/docs`
- **Logging**: Configure logging levels in `backend/app/configs/config.yaml`
- **Dependencies**: Add new packages with `uv add <package>`
- **Environment Variables**: Backend reads from `backend/.env` file for configuration
- **Convenience Scripts**: Use `scripts/run_backend.sh` (or `.ps1` for Windows) for quick startup

### Frontend Development

- **TypeScript**: All components use TypeScript for type safety
- **Tailwind CSS**: Utility-first styling with custom theme configuration
- **Dark Mode**: Theme handled by `next-themes` with system preference detection
- **API Integration**: Backend API calls centralized in `src/lib/backend.ts`
- **Convenience Scripts**: Use `scripts/run_frontend.sh` (or `.ps1` for Windows) for quick startup

## 🚀 Deployment

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

### Environment Variables

For production deployment, ensure the following environment variables are set:

**Frontend** (`.env` in root directory):

```bash
API_HOST=http://backend:8000  # Or your production backend URL
```

**Backend** (`.env` in `backend/` directory):

```bash
# Database directories
DUCK_DIR=./duck_db
LANCE_DIR=./lance_db
GBIF_DIR=./data
IMAGE_DIR=../public/images

# Optional: Custom AI service
UF_AI_URL=your_ai_service_url
UF_AI_API_KEY=your_ai_api_key
```

## 🔌 API Endpoints

The backend provides the following key API endpoints:

### Search & Retrieval

- `GET /api/ml-search/text-search` - Text-based semantic search
- `POST /api/ml-search/image-search` - Image-based similarity search
- `GET /api/db-search/taxon` - Taxonomic data search

### Species Data

- `GET /api/species/{species_name}` - Get detailed species information
- `GET /api/species/{species_name}/similar` - Find similar species

### Images

- `GET /api/images/{species_name}` - Retrieve species images
- `GET /api/images/thumbnail/{species_name}` - Get thumbnail images

### Statistics

- `GET /api/stats/summary` - Dataset statistics and metrics

### AI Chat

- `POST /api/chat` - Conversational AI about biodiversity

For complete API documentation, visit [http://localhost:8000/docs](http://localhost:8000/docs) when running the backend.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **OpenAI CLIP**: Vision-language model for semantic understanding
- **UNICOM**: Advanced computer vision model for biological images
- **LanceDB**: Fast vector database for similarity search
- **FastAPI**: Modern Python web framework
- **Next.js**: React framework with excellent developer experience
- **Leaflet**: Open-source mapping library
- **GBIF**: Global biodiversity data integration
- **Butterfly Dataset Contributors**: High-quality species images and data

---

**BioCosmos** - Exploring biodiversity through the lens of AI 🦋✨
