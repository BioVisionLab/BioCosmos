# Copilot Instructions for BioCosmos

## Project Overview
BioCosmos is a full-stack biodiversity image platform for butterfly species, combining a Next.js/React frontend with a FastAPI/Python backend. It features multi-modal search (text, semantic, image), interactive t-SNE visualizations, and AI-powered chat.

## Architecture & Key Components
- **Frontend (`src/`)**: Next.js (App Router), React, TypeScript, Tailwind CSS, Leaflet.js for maps. Key UI logic in `src/components/` and API calls in `src/app/`.
- **Backend (`backend/app/`)**: FastAPI app (`main.py`), modular routers for search/taxon endpoints, database logic in `database/`, ML/external services in `services/`, and search logic in `searches/`.
- **Data**: DuckDB for local SQL, LanceDB for vector search, image assets in `public/images/`, t-SNE outputs in `tsne_outputs/`.
- **Tools (`tools/`)**: Python scripts for embedding, metadata, and visualization prep.

## Developer Workflows
- **Run Full Stack (Recommended):**
  - `docker-compose up --build` (requires `.env.local` with `OPENAI_API_KEY` and `API_HOST`)
- **Manual Local Dev:**
  - Frontend: `yarn dev` (in project root)
  - Backend: `cd backend && uvicorn app.main:app --reload`
  - Python deps: managed with `uv` (`pip install uv` if missing)
- **Testing:**
  - Backend: `pytest` in `backend/app/tests/`
  - Frontend: (no standard test setup; add tests in `src/` as needed)
- **Data Prep:**
  - Use scripts in `tools/` for embedding images, generating t-SNE, etc.

## Patterns & Conventions
- **API Design:** All backend endpoints are defined in `backend/app/routers/`. Use FastAPI's dependency injection and response models.
- **Search Logic:** Multi-modal search is split into `searches/` and `services/` (CLIP, GBIF, etc.).
- **Database:** Prefer DuckDB for local analytics; LanceDB for vector similarity. Models in `database/model.py`.
- **Frontend Routing:** Next.js App Router with dynamic routes for taxonomy (`src/app/family/[name]/`, etc.).
- **Styling:** Tailwind CSS with custom themes in `tailwind.config.ts`.
- **Environment:** Secrets/config in `.env.local` (never commit this file).

## Integration Points
- **OpenAI API:** Used for chatbot and semantic search (requires key).
- **CLIP Model:** Image embeddings for visual/semantic search (see `services/clip.py`).
- **Leaflet.js:** Interactive map visualizations in frontend.
- **Docker:** Both frontend and backend have Dockerfiles; use Compose for orchestration.

## Examples
- Add a new API endpoint: create a router in `backend/app/routers/`, register in `main.py`.
- Add a new search type: implement logic in `searches/` and connect via router.
- Add a new React component: place in `src/components/`, import in relevant page in `src/app/`.

## References
- See `README.md` (project root) for setup, architecture, and workflow details.
- See `backend/README.md` for backend-specific info.
- Key files: `backend/app/main.py`, `src/app/page.tsx`, `src/components/`, `tools/` scripts.

---
For unclear or missing conventions, ask maintainers for guidance or check recent PRs for examples.
