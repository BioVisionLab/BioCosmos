# Contributing to BioCosmos

Thank you for contributing to BioCosmos! We welcome bug reports, feature suggestions, documentation improvements, and code pull requests.

## Code of Conduct

This project is governed by the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## How to Contribute

- **Report bugs**: Open an issue on GitHub describing what happened, how to reproduce it, and what you expected.
- **Suggest enhancements**: Open an issue to discuss new features or design changes before starting large work.
- **Submit pull requests**: Follow the workflow below.

## Pull Request Workflow

1. Fork the repository and create a branch from `main` (`git checkout -b feature/short-description`). Only `main` is merged into `release` for deployment.
2. Implement your change and add tests (`backend/tests/test_<feature>.py` or `packages/<name>/tests/test_<feature>.py`) for any modified router, query, service, or package.
3. Run the [pre-PR checks](#checks-before-a-pull-request) for the areas you touched.
4. Commit with a short, imperative subject (for example, `Fix image rendering.` or `Reduce caching.`). Keep generated datasets and reports out of commits.
5. Push your branch and open a pull request against `main`. Explain the problem and solution, link related issues, list the verification commands you ran, and attach screenshots for visible UI changes.

> **Never commit** `.env` or `.env.local` files, API keys, local DuckDB or LanceDB databases, model weights, bulk images, or generated files under `reports/` or `analyses/results/`.

## Project Structure

```text
BioCosmos/
├── src/                      # Next.js 16 frontend (App Router, TypeScript, Tailwind CSS 4)
│   ├── app/                  # Pages: species, higher taxa, search, collections, ...
│   │   └── api/              # Route handlers that proxy the backend (API_HOST)
│   ├── components/           # Reusable React components (HigherTaxonPage.tsx shared across ranks)
│   └── lib/                  # API clients and data helpers
├── public/                   # Static frontend assets
│   ├── geo/                  # Country geometry (backend/scripts/export_country_geometry.py)
│   ├── maplibre/             # MapLibre worker, copied at dev/build time (gitignored)
│   └── images/               # Raw source images for ingestion (gitignored)
├── backend/                  # FastAPI backend service (uv workspace member)
│   ├── app/
│   │   ├── main.py           # Entrypoint; startup ingestion and derived-table builds
│   │   ├── configs/          # config.yaml, environment settings, and LLM prompts
│   │   ├── database/         # DuckDB and LanceDB clients, models, and Lance migration
│   │   ├── routers/          # HTTP endpoints (keep thin)
│   │   ├── query/            # DuckDB and LanceDB query logic
│   │   └── services/         # Domain logic and external/ML integrations
│   ├── scripts/              # Maintenance and export scripts
│   ├── tests/                # Backend pytest suite
│   ├── static/webp/          # Processed full-size and thumbnail WebP images (gitignored)
│   └── Dockerfile            # Built with the repository root as context
├── packages/                 # Python packages (uv workspace members; see packages/README.md)
│   ├── harmonize-core/       # Shared DuckDB, config, country/place normalization, and reporting
│   ├── colharmonize/         # Catalogue of Life taxonomic matching (also used by backend)
│   ├── geoharmonize/         # GADM coordinate validation
│   ├── instharmonize/        # Institution code resolution via GBIF (used by backend)
│   ├── morphospace/          # Precomputed dorso-ventral UNICOM morphospaces
│   ├── similarity/           # Precomputed visually similar species
│   └── plannerbench/         # Agent-search LLM planner benchmark
├── analyses/                 # Publication notebooks and vector-index benchmarks (separate uv project)
├── reports/                  # Generated package run artifacts (gitignored; see reports/README.md)
├── scripts/                  # Local launch helpers (run_backend.sh, run_frontend.sh, ...)
├── pyproject.toml, uv.lock   # Root uv workspace and shared lockfile
├── package.json, bun.lock    # Frontend dependencies
├── docker-compose.yml        # Multi-container setup (GPU-enabled backend)
└── Dockerfile.frontend
```

## Local Development Setup

### Prerequisites

- **Git**
- **Bun 1.3.11** (pinned in `package.json`) for frontend dependencies and scripts.
- **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)**:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Hardware**: The backend loads CLIP and UNICOM models at startup. A CUDA or Apple Silicon GPU is used automatically when available; CPU works but image embedding is slow. Plan for tens of gigabytes of disk space for the full dataset (embeddings alone take ~15 GB).
- **Network on first start**: Downloads CLIP (`openai/clip-vit-base-patch32`) into `~/.cache/huggingface` and UNICOM weights into `~/.cache/unicom`. Startup also fetches LepTraits from GitHub and resolves uncached institution codes via GBIF (both degrade gracefully offline).
- **Optional**: Docker with Docker Compose; an OpenAI-compatible LLM endpoint for agentic search and AI species summaries.

### 1. Clone and install dependencies

```bash
git clone <repository-url>
cd BioCosmos
bun install
uv sync --all-packages
```

`uv sync --all-packages` installs `backend` and all seven packages under `packages/` into a single `.venv` using the root `uv.lock`.

### 2. Obtain the data

The repository does not bundle dataset files. Place your inputs in the directories configured in step 3:

| Input | Directory variable | Purpose |
| :--- | :--- | :--- |
| Specimen images (`.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`), any folder depth | `$IMAGE_DIR` | Embeddings, processed WebP images, and thumbnails. The filename stem must match `img_id` in the metadata. |
| Image metadata (`image_metadata.file` in `config.yaml`, Parquet) | `$IMAGE_META_DIR` | Loaded into `image_meta_source` and exposed via the filtered `image_meta` view. |
| GBIF occurrence download (`gbif.file`, TSV) | `$GBIF_DIR` | Loaded into `gbif_meta` for locality and institution provenance. |
| Extracted Catalogue of Life ColDP archive (`NameUsage.tsv`, plus optional `VernacularName.tsv`, `TypeMaterial.tsv`, `Reference.tsv`) | `$COL_DIR` | Taxonomic harmonization (`image_meta_taxonomy`). Optional, but required for taxonomic classification. |
| GADM 4.1 GeoPackage (`gadm_410-levels.gpkg`) | `$GADM_DIR` | Offline coordinate validation (`geoharmonize`). |

If you already have prebuilt `biocosmos.duckdb` and `biocosmos.lance` databases, place them in `$DUCK_DIR` and `$LANCE_DIR` along with `backend/static/webp/` and skip to [step 6](#6-run-the-application).

### 3. Configure the environment

**Frontend**: Create `.env.local` in the repository root:

```bash
API_HOST=http://127.0.0.1:8000
```

**Backend**: Create `backend/.env` using **absolute paths** (the backend runs from `backend/`, whereas package CLIs run from the repository root):

```bash
# Required paths
DUCK_DIR=/absolute/path/to/BioCosmos/backend/duck_db
LANCE_DIR=/absolute/path/to/BioCosmos/backend/lance_db_lite
IMAGE_DIR=/absolute/path/to/BioCosmos/public/images
IMAGE_META_DIR=/absolute/path/to/BioCosmos/backend/data
GBIF_DIR=/absolute/path/to/BioCosmos/backend/data

# Optional, but required for Catalogue of Life taxonomy (directory containing NameUsage.tsv)
COL_DIR=/absolute/path/to/catalogue-of-life-col-dp

# Recommended: contact email for CrossRef (Literature tab) polite pool
# CROSSREF_MAILTO=you@example.org

# Recommended: contact email and API key for NCBI (Genetics tab; 10 req/s with key vs. 3 req/s without)
# NCBI_EMAIL=you@example.org
# NCBI_API_KEY=your_ncbi_api_key

# Optional: OpenAI-compatible LLM endpoint for agentic search and summaries
# LLM_API_URL=your_llm_endpoint
# LLM_API_KEY=your_api_key
```

The backend opens `$DUCK_DIR/biocosmos.duckdb` and `$LANCE_DIR/biocosmos.lance`, creating directories if needed.

Before running offline CLI tools from the repository root, load `backend/.env` into your shell and set `GADM_DIR`:

```bash
set -a
source backend/.env
set +a
export GADM_DIR=/absolute/path/to/gadm
```

### 4. First build: ingest raw data

Startup ingestion is configured in `backend/app/configs/config.yaml`. Checked-in defaults skip raw ingestion assuming prebuilt databases exist. For an initial build from raw files, set these three flags to `false`:

| Setting in `backend/app/configs/config.yaml` | What it ingests |
| :--- | :--- |
| `image_metadata.skip` | Loads raw metadata into `image_meta_source` and publishes the `image_meta` view |
| `gbif.skip` | Loads GBIF occurrences into `gbif_meta` |
| `embedder.skip` | Computes CLIP and UNICOM embeddings into LanceDB and writes WebP images/thumbnails to `backend/static/webp/` |

Taxonomy (`col`), traits (`leptrait`), locality (`image_meta_locality`), provenance (`image_meta_provenance`), and institutions (`institution_directory`) run automatically and are guarded by input fingerprints. To test on a small subset first, set `images.limit` in `config.yaml`.

Start the backend and wait for `Application startup completed successfully.`:

```bash
./scripts/run_backend.sh
```

Once ingestion completes, set `image_metadata.skip`, `gbif.skip`, and `embedder.skip` back to `true`, then stop the backend (`Ctrl+C`) before running step 5.

### 5. Build derived tables (with the backend stopped)

DuckDB allows only a single writer, and the running API holds `biocosmos.duckdb` open read-write. **Stop the backend** before running any offline CLI against the live database:

1. **Vector search indexes**: Set `search_index.build_vector: true` in `backend/app/configs/config.yaml`, start the backend once so it builds the IVF-PQ indexes in LanceDB, then set `search_index.build_vector: false` and stop the backend.
2. **Coordinate validation (`main.image_meta_coordinates`)**: Requires `main.image_meta_locality` (built by the backend in step 4) and `$GADM_DIR/gadm_410-levels.gpkg`. Do not pass `main.image_meta` directly because `country_code` and `state_province` come from `image_meta_locality`:
   ```bash
   uv run geoharmonize inspect --db "$DUCK_DIR/biocosmos.duckdb" \
     --table main.image_meta_locality \
     --map source_id=img_id --map country=country_code --map adm1=state_province

   uv run geoharmonize integrate --db "$DUCK_DIR/biocosmos.duckdb" \
     --table main.image_meta_locality --gadm "$GADM_DIR/gadm_410-levels.gpkg" \
     --map source_id=img_id --map country=country_code --map adm1=state_province \
     --into main.image_meta_coordinates --reports-dir reports
   ```
   (Add `--replace` if rebuilding an existing `main.image_meta_coordinates` table.)
3. **Visually similar species (`species_similarity`)**:
   ```bash
   uv run similarity run --db "$DUCK_DIR/biocosmos.duckdb" --lance-dir "$LANCE_DIR/biocosmos.lance"
   ```
4. **Dorso-ventral morphospaces (`morphospace_*` tables)**:
   ```bash
   uv run morphospace run --db "$DUCK_DIR/biocosmos.duckdb" --lance-dir "$LANCE_DIR/biocosmos.lance"
   uv run morphospace integrate --db "$DUCK_DIR/biocosmos.duckdb" --replace
   ```
5. **Country geometry (`public/geo/countries-110m.json`)**: Already committed; regenerate only if country lookup rules change:
   ```bash
   cd backend && uv run python scripts/export_country_geometry.py
   ```

> **Optional taxonomy CLI reports**: The backend harmonizes taxonomy at startup, so `colharmonize` is not needed to run the site. To export standalone taxonomy reports or plots, run:
> ```bash
> uv run colharmonize run --db "$DUCK_DIR/biocosmos.duckdb" \
>   --table main.image_meta --map scientific_name=species \
>   --map family=family --map order=order --map class=class --map kingdom=kingdom \
>   --col "$COL_DIR/NameUsage.tsv" --reports-dir reports --csv --plot
> ```
> See [`packages/README.md`](packages/README.md) and [`reports/README.md`](reports/README.md) for details on all seven workspace packages.

#### Upgrading an older LanceDB collection

If startup logs a warning that the LanceDB table needs migration (v2 manifests, `img_path`, compaction, `img_id` BTREE index), stop the backend and run:

```bash
cd backend
uv run --env-file .env python scripts/migrate_lance.py          # dry run
uv run --env-file .env python scripts/migrate_lance.py --apply  # apply migration
```

Add `--drop-legacy-columns` to drop stored image bytes (refused unless all images exist in `backend/static/webp/`) and `--reindex` to retrain vector indexes. `table.restore(<version>)` can undo a migration for seven days.

### 6. Run the application

```bash
# Terminal 1: FastAPI backend with auto-reload on port 8000
./scripts/run_backend.sh

# Terminal 2: Next.js frontend with Turbopack on port 3000
bun run dev
```

Windows users can run the `.ps1` scripts in `scripts/`.

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Interactive API docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 7. Production build

```bash
bun run build                # type-checks and builds the frontend
bun run start                # serves the production frontend on port 3000
./scripts/run_backend_prod.sh
```

Both `bun run dev` and `bun run build` automatically copy the MapLibre worker into `public/maplibre/`.

## Database Rules: Excluded Families and Taxonomic Overrides

- **Always query `image_meta`, never `image_meta_source`**: Raw image metadata is ingested into `image_meta_source`. At startup, the backend publishes `image_meta` as a filtered view that excludes families in `image_metadata.exclude_families` (`backend/app/configs/config.yaml`; currently Castniidae moths). `image_meta_input` drops records with an excluded recorded family, and records whose harmonized family resolves to an excluded family are placed in `image_meta_excluded` and omitted from `image_meta` and `image_meta_taxonomy`.
- **Obsolete families and pinned names**: `col.family_synonyms` maps legacy Catalogue of Life families lacking a superfamily (Satyridae, Danaidae, Acraeidae, Amathusiidae, Libytheidae, Arctiidae, etc.) to their current family. `col.taxon_overrides` pins specific recorded names to a CoL usage ID (`match_method = 'MANUAL_OVERRIDE'`). Cross-order homonyms outside the recorded order (or `col.clade_value` when `col.clade_rank` is `order`) are rejected with `ORDER_MISMATCH`.
- **Rebuilding after config changes**: Whenever you change `image_metadata.exclude_families`, `col.family_synonyms`, or `col.taxon_overrides`, restart the backend so `image_meta` and `image_meta_taxonomy` update, stop the backend, and re-run `similarity run`, `morphospace run`/`integrate`, and the notebooks in `analyses/`.

## Testing

### Checks before a pull request

CI runs backend and package checks whenever `backend/**`, `packages/**`, `pyproject.toml`, or `uv.lock` changes. For frontend changes, run ESLint/Prettier and a production build.

**Backend** (must run from `backend/`, which resolves `static/` relatively):

```bash
cd backend
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uvx pyright --pythonpath ../.venv/bin/python app scripts tests
```

**Packages** (run from the repository root; 100-character line limit, Python 3.12):

```bash
uv run --package harmonize-core pytest packages/harmonize-core/tests -q
uv run --package colharmonize pytest packages/colharmonize/tests -q
uv run --package geoharmonize pytest packages/geoharmonize/tests -q
uv run --package instharmonize pytest packages/instharmonize/tests -q
uv run --package morphospace pytest packages/morphospace/tests -q
uv run --package similarity pytest packages/similarity/tests -q
uv run --package plannerbench pytest packages/plannerbench/tests -q
uv run ruff check packages/ && uv run ruff format --check packages/
```

**Frontend** (run from the repository root):

```bash
bun run lint
bun run build
```

`bun run lint` runs ESLint (`eslint.config.mjs`) followed by `prettier --check .`. Use `bun run lint:fix` or `bun run format` to apply formatting fixes automatically.

## Caching and Cache Invalidation

Responses are cached across multiple layers, including visitors' browsers where the server cannot clear them. Decide how a cached response will be invalidated **before** setting its TTL.

### Where responses are cached

- **Browser and CDN (HTTP cache)**: Controlled by `Cache-Control` and `ETag` headers defined in `backend/app/routers/http_cache.py` and forwarded by Next.js route handlers in `src/app/api/`. Entries live up to 30 days (higher-taxon overviews) or 1 day (similarity, literature, genetics). They retire only on expiration, an `ETag` mismatch on revalidation, or a URL change.
- **Next.js data cache**: Controlled by `fetch(..., { next: { revalidate } })` in `src/lib/`. Cleared on frontend redeploy.
- **Backend in-process caches**: `TtlCache` (`backend/app/services/ttl_cache.py`) caches CrossRef and NCBI responses for 7 days, and `agent_cache.py` caches agent searches for 15 minutes. Cleared by restarting the backend.
- **Precomputed DuckDB tables**: Built by `geoharmonize integrate`, `similarity run`, and `morphospace integrate`; kept until rebuilt.

### Choosing an invalidation mechanism

Use the first option that fits:

1. **`ETag` tied to data source**: Build the `ETag` from the ingestion fingerprint (like `_overview_etag` in `backend/app/routers/species_data.py`) so re-ingestion invalidates cached entries on revalidation.
2. **Payload version constant**: When code changes alter the response shape or meaning for the same inputs:
   - If the endpoint uses an `ETag`, bump the version constant included in the `ETag` (for example, `OVERVIEW_PAYLOAD_VERSION` in `backend/app/query/higher_taxa.py`).
   - If the endpoint does not use an `ETag`, bump the version query parameter in the request URL (for example, `GENETICS_PAYLOAD_VERSION` in `src/lib/genetic.ts`, sent as `&v=`).
3. **Short `max-age` alone**: Use only when the payload schema is stable and regenerated on its own schedule.

### When to bump a payload version

Bump the version (and update the comment next to the constant) whenever a change would cause new frontend code to render an old cached response incorrectly:

- Adding a field that the UI renders
- Removing or renaming a field
- Changing how a value is calculated or what it represents
- Fixing a bug that cached bad data

Keep the frontend resilient to older payloads during rollouts using optional chaining and sensible defaults.

### Rules for new endpoints

- Define `Cache-Control` policies in `backend/app/routers/http_cache.py` and return responses with `cached_json`.
- Never cache errors: send `NO_STORE` for 4xx and 5xx responses.
- Cache partial upstream results briefly (5 minutes in both HTTP headers and `TtlCache`) so transient outages recover quickly.
- Next.js route proxies in `src/app/api/` should forward the backend's `Cache-Control` and default to `no-store` (except content-addressed image bytes by ID, which are `immutable`).
- Cache external API calls (CrossRef, NCBI, GBIF) in the backend service with bounded size, shared in-flight requests, and rate-limit pacing (`crossref.py`, `genetics.py`).

### Verifying caching behavior

Inspect headers directly from the backend and through the Next.js proxy:

```bash
curl -sI "http://localhost:8000/species/Danaus%20plexippus/genetics"
curl -s -D - -o /dev/null "http://localhost:3000/api/genetics?species=Danaus%20plexippus&v=2"
```

## Deployment

### Docker Compose

`docker-compose.yml` builds both containers and mounts the data directories into the backend container. The backend reserves an NVIDIA GPU by default (remove the `deploy` block for CPU-only hosts).

```bash
docker compose up --build      # build and start in foreground
docker compose up -d           # start in background
docker compose down            # stop
```

### Manual Docker / Podman builds

Build both images with the **repository root** as the build context so the backend image can access `pyproject.toml`, `uv.lock`, and `packages/`:

```bash
docker build -t biocosmos-backend -f backend/Dockerfile .
docker build -t biocosmos-frontend -f Dockerfile.frontend .
```

In containerized deployments, set `col.cache_dir` in `backend/app/configs/config.yaml` to a path inside `DUCK_DIR` so the Catalogue of Life index persists across container restarts.

## API Endpoints

For full request/response schemas, start the backend and visit [http://localhost:8000/docs](http://localhost:8000/docs).

### Frontend proxy routes (`src/app/api/`)

- **Search**: `GET /api/db-search`, `GET /api/ml-search/text`, `POST /api/ml-search/image`, `GET /api/ml-search/agent`, `GET /api/ml-search/similarity`
- **Species & taxonomy**: `GET /api/taxon-search`, `GET /api/taxonomy/species`, `GET /api/taxonomy/codes`, `GET /api/gbif-taxon`, `GET /api/specimens`, `GET /api/species-coordinates`, `GET /api/geography/codes`
- **External integrations**: `GET /api/genetics`, `GET /api/literature`, `GET /api/higher-taxon-literature`
- **Morphospace & statistics**: `GET /api/morphospace/[...path]`, `GET /api/stats/taxon`, `GET /api/stats/embeddings`
- **Images & health**: `GET /api/images/id`, `GET /api/images/id/metadata`, `GET /api/images/metadata`, `GET /api/images/species`, `GET /api/status`

### Backend FastAPI routes (`backend/app/routers/`)

- **Search**: `GET /search/db`, `GET /search/text`, `POST /search/image`, `GET /search/agent`
- **Species profiles**: `GET /species/featured`, `GET /species/{scientific_name}/biology`, `GET /species/{scientific_name}/taxonomy`, `GET /species/{scientific_name}/similar`, `GET /species/{scientific_name}/specimens`, `GET /species/{scientific_name}/coordinates`, `GET /species/{scientific_name}/genetics`, `GET /species/{scientific_name}/literature`, `GET /summarize/{species_name}`
- **Higher taxa**: `GET /order/{order_name}`, `GET /suborder/{name}`, `GET /superfamily/{name}`, `GET /family/{family_name}`, `GET /subfamily/{name}`, `GET /tribe/{name}`, `GET /subtribe/{name}`, `GET /genus/{genus_name}`, `GET /genus/{genus_name}/subgenus/{subgenus_name}`, and their `/literature` sub-routes
- **GBIF classification & code lookups**: `GET /family/{family_name}/classification`, `GET /genus/{genus_name}/classification`, `GET /species/{genus}/{specific_epithet}/classification`, `GET /taxonomy/codes`, `GET /geography/codes`
- **Morphospace & statistics**: `GET /morphospace/species/{species}`, `GET /morphospace/{rank}/{name}`, `GET /stats/taxon`, `GET /stats/embeddings`, `GET /stats/country`, `GET /stats/country/{country_code}`
- **Images & health**: `GET /image/id/{image_id}`, `GET /image/id/{image_id}/thumbnail`, `GET /image/id/{image_id}/metadata`, `GET /image/{scientific_name}/metadata`, `GET /image/{scientific_name}/thumbnail`, `GET /image/{scientific_name}/high-resolution`, `GET /status`

## Coding Standards

- **American English**: Always use American English spelling (`color`, `harmonize`, `behavior`) in identifiers, comments, docstrings, UI copy, documentation, and commit messages.
- **Control-flow spacing (Python and TypeScript/JavaScript)**: Place one blank line before and after every `for` loop, `if` statement (including its `elif`/`else` branches), and `try` statement (including `except`/`else`/`finally`), before every `return`, and after any docstring followed by code. Omit the blank line immediately after a line that opens a block (`def`, `if`, `else`, etc.) or immediately before a line that closes a block. Never stack multiple blank lines. ESLint enforces this on the frontend (`bun run lint:fix`).
- **Frontend (TypeScript & React)**:
  - Two-space indentation, strict TypeScript, `PascalCase` for components and types, `camelCase` for functions and variables, and `@/` imports for `src/`.
- **Backend & Packages (Python 3.12+)**:
  - Four-space indentation, `snake_case` modules and functions, and typed FastAPI/Pydantic models. Keep routers thin and place domain logic in `query/` or `services/`.
  - Place all `import` statements at the top of the module, never inside a function or method (including in tests; enforced by Ruff `PLC0415`).
  - Never define a nested function (`def` or `lambda` workaround) inside another function; use a module-level helper or method and pass state as arguments or with `functools.partial`.
  - Code must pass Pyright in `standard` mode with zero errors. Narrow `Optional` types rather than suppressing errors, and never use a bare `# type: ignore`.
