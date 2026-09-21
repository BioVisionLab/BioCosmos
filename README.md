# BioCosmos - Biodiversity Image Platform

[![Backend-Tests](https://github.com/agporto/BioCosmos/workflows/Backend-Tests/badge.svg)](https://github.com/agporto/BioCosmos/actions)

A personalized, museum-quality biodiversity image platform that combines machine learning with intuitive web interfaces to explore and identify butterfly species. Built with Next.js, Python, and advanced computer vision technologies.

## Features

- **Multi-modal search**: Find species by name, natural language, or image.
- **Interactive visualization**: Explore visual similarity through zoomable UMAP maps.
- **Taxonomic navigation**: Browse the taxonomy tree with representative images.
- **Species profiles**: View descriptions, conservation status, image galleries, and geographic distributions.
- **AI integration**: CLIP, UNICOM, and agentic search connect images and species data.
- **Responsive interface**: Desktop and mobile layouts with dark and light themes.

## Architecture

### Frontend Stack

- **Next.js**: React-based framework with App Router.
- **React**: Component-based user interface library.
- **TypeScript**: Type-safe development.
- **Tailwind CSS**: Utility-first styling with custom themes.
- **MapLibre GL JS**: Interactive vector maps for geographic distribution, with basemaps from OpenFreeMap.
- **Lucide React**: Clean, customizable iconography.

### Backend Stack

- **FastAPI**: Modern, high-performance web framework for APIs.
- **Python 3.12+**: Core backend language.
- **LanceDB**: Vector database for embedding storage and similarity search.
- **DuckDB**: In-process SQL OLAP database for structured metadata and taxonomy.
- **CLIP**: OpenAI's vision-language model for semantic search.
- **UNICOM**: Computer vision model optimized for fine-grained biological image similarity.
- **Polars**: High-performance DataFrame library for data processing.
- **Transformers**: Hugging Face library for ML model integration.
- **PyTorch**: Deep learning framework for model inference.

### Data Harmonization

Offline tools under `packages/`, members of the same uv workspace as the backend:

- **colharmonize**: Matches occurrence species names against a Catalogue of Life release.
- **geoharmonize**: Validates occurrence coordinates against GADM administrative geography.
- **harmonize-core**: Shared DuckDB, configuration, and reporting primitives for both.

Each run writes a DuckDB database and a JSON manifest to `reports/`, recording a
SHA-256 digest of every artifact it produced. See [packages/](packages/README.md)
and [reports/](reports/README.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, development, testing, deployment, API details, and the pull request workflow.

## License

This project is licensed under the MIT License - see the LICENSE file for details .

## Acknowledgments

- **OpenAI CLIP**: Vision-language model for semantic understanding
- **UNICOM**: Advanced computer vision model for biological images
- **LanceDB**: Fast vector database for similarity search
- **FastAPI**: Modern Python web framework
- **Next.js**: React framework with excellent developer experience
- **MapLibre GL JS**: Open-source mapping library (basemaps served by OpenFreeMap)
- **GBIF**: Global biodiversity data integration
- **Butterfly Dataset Contributors**: High-quality species images and data
- **Mammal Diversity Database**: Feature inspiration for species profiles and taxonomy navigation

---

**BioCosmos** - Exploring biodiversity through the lens of AI.
