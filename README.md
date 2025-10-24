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

### Backend Services

- **Python**: The core language for the backend.
- **FastAPI**: A modern, fast (high-performance) web framework for building APIs.
- **DuckDB**: An in-process SQL OLAP database management system.
- **UNICOM**: A model for advanced computer vision tasks, including semantic search.
- **Pillow**: A powerful image processing library for Python.

## 📁 Project Structure

```bash
biocosmos/
├── backend/                  # Python backend (FastAPI)
│   ├── app/                    # Core application code
│   │   ├── main.py             # FastAPI entrypoint
│   │   ├── database/           # Database models and connections
│   │   ├── routers/            # API endpoints
│   │   ├── searches/           # Search logic
│   │   └── services/           # ML and external services
│   ├── Dockerfile              # Backend Dockerfile
│   └── pyproject.toml          # Python dependencies
├── src/                      # Next.js frontend
│   ├── app/                    # App Router pages and layouts
│   ├── components/             # React components
│   └── lib/                    # Helper functions and utilities
├── public/                   # Static assets (images, etc.)
├── tools/                    # Helper scripts for data processing
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile.frontend       # Frontend Dockerfile
└── package.json              # Frontend dependencies
```

## 🚀 Local Development Setup

### Prerequisites

- **Node.js** (v18 or higher)
- **Python** (v3.10 or higher)
- **Git**
- **Docker** and **Docker Compose**
- **OpenAI API Key** (for chatbot functionality)

### Running with Docker (Recommended)

This is the easiest way to get started with BioCosmos. With Docker and Docker Compose, you can spin up the entire application with a single command.

1. **Clone the Repository**

    ```bash
    git clone <repository-url>
    cd biocosmos
    ```

2. **Environment Configuration**

    Create a `.env.local` file in the root directory:

    ```bash
    # This is the API host for production, change it to development address if needed
    API_HOST=http://0.0.0.0:8000
    # Dev API host if you run development server:
    # API_HOST=http://127.0.0.1:8000
    ```

3. **Build and Run with Docker Compose**

    ```bash
    docker-compose up --build
    ```

4. **Access the Application**

    Open [http://localhost:3000](http://localhost:3000) in your browser.

### Manual Setup

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

    We use [uv](https://docs.astral.sh/uv/) to manage the dependencies for the Python backend service. If you don't have `uv` installed, you can install it via pip:

    ```bash
    pip install uv
    ```

    Other intallation methods are available in the [uv documentation](https://docs.astral.sh/uv/installation).

4. **Environment Configuration**

    Create a `.env.local` file in the root directory:

    ```bash
    OPENAI_API_KEY=your_openai_api_key_here
    # This is the API host for production, change it to development address if needed
    API_HOST=http://0.0.0.0:8000
    ```

5. **Prepare the Dataset**

    Ensure your butterfly images are organized in `public/images/`.

6. **Start the Services**

    **Terminal 1 - Frontend:**

    ```bash
    yarn dev
    ```

    **Terminal 2 - Backend Service:**

    ```bash
    cd backend
    uvicorn app.main:app --reload
    ```

7. **Access the Application**

    Open [http://localhost:3000](http://localhost:3000) in your browser.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **iNaturalist**: Inspiration for biodiversity platforms
- **OpenAI CLIP**: Computer vision capabilities
- **Leaflet**: Interactive mapping functionality
- **Next.js Team**: Excellent React framework
- **Butterfly Dataset Contributors**: High-quality species images

---

**BioCosmos** - Exploring biodiversity through the lens of AI 🦋✨
