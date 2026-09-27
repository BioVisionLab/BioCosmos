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

1. Fork the repository and branch from `main`
   (`git checkout -b feature/amazing-feature`). Only `main` may be merged into
   `release`, which deploys the site.
2. Make your change, with tests for any changed router, query, or service.
3. Run the [checks](#checks-before-a-pull-request) for the parts you touched.
4. Commit with a short, imperative subject (`Fix image rendering.`). Keep
   generated datasets out of code commits.
5. Push the branch and open a pull request against `main`. Explain the problem
   and the solution, link related issues, list the commands you ran, and
   include screenshots for visible UI changes.

Never commit `.env` or `.env.local` files, API keys, DuckDB or LanceDB files,
model weights, images, or anything generated under `reports/`.

## Project Structure

```text
BioCosmos/
├── src/                      # Next.js 16 frontend (App Router, TypeScript, Tailwind 4)
│   ├── app/                    # Pages: species, genus, family, order, search, collections, ...
│   │   └── api/                # Route handlers that proxy the backend (API_HOST)
│   ├── components/             # React components
│   └── lib/                    # Data fetching and helpers
├── public/                   # Static assets
│   ├── geo/                    # Country geometry (backend/scripts/export_country_geometry.py)
│   ├── maplibre/               # MapLibre worker, copied at dev/build time (git-ignored)
│   └── images/                 # Source images for ingestion (git-ignored)
├── backend/                  # FastAPI service (uv workspace member)
│   ├── app/
│   │   ├── main.py             # Entrypoint; startup ingestion and table builds
│   │   ├── configs/            # config.yaml, settings, LLM prompts
│   │   ├── database/           # DuckDB and LanceDB clients, models, Lance migration
│   │   ├── routers/            # HTTP endpoints (keep them thin)
│   │   ├── query/              # Data access
│   │   └── services/           # Domain logic and external/ML integrations
│   ├── scripts/                # Maintained maintenance and export scripts
│   ├── tests/                  # Backend pytest suite
│   ├── static/webp/            # Processed images and thumbnails (git-ignored)
│   └── Dockerfile              # Built with the repository root as context
├── packages/                 # Python tools (uv workspace members)
│   ├── harmonize-core/         # Shared DuckDB, config, and reporting primitives
│   ├── colharmonize/           # Catalogue of Life name matching (also used by the backend)
│   ├── geoharmonize/           # GADM coordinate validation
│   ├── instharmonize/          # Institution code resolution (used by the backend)
│   ├── morphospace/            # Precomputed UNICOM morphospaces
│   ├── similarity/             # Precomputed visually similar species
│   └── plannerbench/           # Agent-search planner benchmarks
├── analyses/                 # Publication notebooks and index benchmarks (separate uv project)
├── reports/                  # Generated run artifacts (git-ignored)
├── scripts/                  # Launch helpers (run_backend.sh, run_frontend.sh, ...)
├── tools/                    # Outdated and unused; do not use
├── pyproject.toml, uv.lock   # uv workspace root and its single lockfile
├── package.json, bun.lock    # Frontend dependencies
├── docker-compose.yml        # Both services, GPU-enabled backend
└── Dockerfile.frontend
```

## Local Development Setup

### Prerequisites

- **Git**
- **Bun 1.3.11** (pinned in `package.json`). Bun runs the build scripts, so a
  separate Node.js install is optional.
- **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)**:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- **Hardware:** the backend loads the CLIP and UNICOM models at every start.
  A CUDA or Apple-silicon GPU is used automatically when present; a CPU works
  but embedding images is slow. Plan for tens of gigabytes of disk for the full
  collection (the image embeddings alone are about 15 GB).
- **Network on first start:** CLIP (`openai/clip-vit-base-patch32`) downloads
  from Hugging Face into `~/.cache/huggingface`, and the UNICOM weights into
  `~/.cache/unicom`. The backend also fetches LepTraits from GitHub and
  resolves institution codes against GBIF; both degrade gracefully offline.
- **Optional:** Docker with Docker Compose (and the NVIDIA container toolkit
  for the GPU reservation in `docker-compose.yml`); an OpenAI-compatible LLM
  endpoint for agentic search and summaries.

### 1. Clone and install

```bash
git clone <repository-url>
cd BioCosmos
bun install
uv sync --all-packages
```

`uv sync --all-packages` installs the backend and every package in
`packages/` into one `.venv` from the root `uv.lock`. Add `--dev` for pytest
and Ruff.

### 2. Obtain the data

The repository ships no data. You need:

| Input | Where it goes | Used for |
| ----- | ------------- | -------- |
| Specimen images (`.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`), any folder depth | `$IMAGE_DIR` | Embeddings, processed images, thumbnails. The file name without its extension is the image ID and must match `img_id` in the metadata. |
| Image metadata (`image_metadata.file` in `config.yaml`, currently a parquet file) | `$IMAGE_META_DIR` | `image_meta` |
| GBIF occurrence download (`gbif.file`, a TSV) | `$GBIF_DIR` | Locality and provenance |
| Extracted Catalogue of Life ColDP release (`NameUsage.tsv`, plus optional `VernacularName.tsv`, `TypeMaterial.tsv`, `Reference.tsv`) | `$COL_DIR` | Taxonomy. Optional, but without it the site has no classification. |
| GADM 4.1 GeoPackage (`gadm_410-levels.gpkg`) | `$GADM_DIR` | Offline coordinate validation only |

If a maintainer gives you prebuilt `biocosmos.duckdb` and `biocosmos.lance`
files, put them in `$DUCK_DIR` and `$LANCE_DIR`, together with the processed
images in `backend/static/webp/`, and skip the first build below.

### 3. Configure the environment

**Frontend:** create `.env.local` in the repository root:

```bash
API_HOST=http://127.0.0.1:8000
```

**Backend:** create `backend/.env`. Use absolute paths: the backend runs from
`backend/`, while the package CLIs run from the repository root, so relative
paths would point at different directories.

```bash
# Required. The backend refuses to start without these.
DUCK_DIR=/absolute/path/to/BioCosmos/backend/duck_db
LANCE_DIR=/absolute/path/to/BioCosmos/backend/lance_db_lite
IMAGE_DIR=/absolute/path/to/BioCosmos/public/images
IMAGE_META_DIR=/absolute/path/to/BioCosmos/backend/data
GBIF_DIR=/absolute/path/to/BioCosmos/backend/data

# Optional, but required for Catalogue of Life taxonomy. A directory
# containing an extracted ColDP NameUsage.tsv, not the file itself.
COL_DIR=/absolute/path/to/catalogue-of-life-col-dp

# Recommended: contact address sent to CrossRef for the Literature tab.
# Without it, requests use CrossRef's slower anonymous public pool.
# CROSSREF_MAILTO=you@example.org

# Recommended: contact address and API key for NCBI (Genetics tab).
# The email falls back to CROSSREF_MAILTO. Without a key, NCBI allows
# 3 requests per second instead of 10.
# NCBI_EMAIL=you@example.org
# NCBI_API_KEY=your_ncbi_api_key

# Optional: OpenAI-compatible LLM endpoint for agentic search and summaries.
# LLM_API_URL=your_llm_endpoint
# LLM_API_KEY=your_api_key
```

The backend opens `$DUCK_DIR/biocosmos.duckdb` and
`$LANCE_DIR/biocosmos.lance`, creating the directories if needed. Keep `.env`
files out of Git.

For the offline package commands, load `backend/.env` into your shell from the
repository root and set the GADM path:

```bash
set -a
source backend/.env
set +a
export GADM_DIR=/absolute/path/to/gadm
```

### 4. First build: ingest the data

Startup ingestion is controlled by `backend/app/configs/config.yaml`. The
checked-in defaults assume the databases already exist, so for a first build
from raw data set these to `false`:

| Setting | Ingests |
| ------- | ------- |
| `image_metadata.skip` | The metadata file into `image_meta_source`, published as the `image_meta` view |
| `gbif.skip` | The GBIF occurrences into `gbif_meta` |
| `embedder.skip` | Every image in `$IMAGE_DIR`: CLIP and UNICOM embeddings into LanceDB, and processed images and thumbnails into `backend/static/webp/` |

Taxonomy (`col`), traits (`leptrait`), locality, provenance, and institutions
stay on. Each is guarded by a fingerprint, so a later start with unchanged
inputs costs almost nothing. To try the pipeline on a sample first, set
`images.limit` to a small number; the embedder skips images it already has.
Tune `embedder.device` and `embedder.batch_size` to your hardware.

Then start the backend and wait for `Application startup completed
successfully.` in the log:

```bash
./scripts/run_backend.sh
```

Embedding the full collection takes hours, even on a GPU. Once it finishes, set
the three `skip` settings back to `true`, so later starts don't re-read the
sources.

### 5. Build the derived data

With the backend **stopped** (DuckDB allows one writer, and the API keeps the
file open), run these from the repository root. Each writes a table the
backend only reads; until it exists, the matching section of the site is
hidden or empty.

1. **Vector indexes.** Set `search_index.build_vector: true`, start the backend
   once, then set it back to `false`. Without the IVF-PQ indexes, similarity
   search falls back to a brute-force scan: correct, but seconds rather than
   milliseconds.
2. **Coordinate validation** (`main.image_meta_coordinates`). See
   [Data Preparation](#data-preparation): the backend must have built
   `main.image_meta_locality` first.
3. **Visually similar species** (`species_similarity`):

   ```bash
   uv run similarity run --db "$DUCK_DIR/biocosmos.duckdb" --lance-dir "$LANCE_DIR/biocosmos.lance"
   ```

4. **Morphospaces** (the `morphospace_*` tables):

   ```bash
   uv run morphospace run --db "$DUCK_DIR/biocosmos.duckdb" --lance-dir "$LANCE_DIR/biocosmos.lance"
   uv run morphospace integrate --db "$DUCK_DIR/biocosmos.duckdb" --replace
   ```

5. **Country geometry** (`public/geo/countries-110m.json`, already committed;
   regenerate it only when the country lookup changes):

   ```bash
   cd backend && uv run python scripts/export_country_geometry.py
   ```

Rerun steps 1, 3, and 4 whenever the embeddings change, and steps 3 and 4
whenever the image metadata or `image_metadata.exclude_families` changes (see
`AGENTS.md`).

#### Upgrading an existing LanceDB collection

Collections built before images moved to disk keep the image bytes in the
table and lack `img_path`. The backend logs a warning at startup when this
applies. With the backend stopped:

```bash
cd backend
uv run --env-file .env python scripts/migrate_lance.py
uv run --env-file .env python scripts/migrate_lance.py --apply
```

The first command is a dry run that lists the steps. `--drop-legacy-columns`
also removes the stored image bytes, and is refused unless every image is in
`backend/static/webp/`. `--reindex` retrains the vector indexes. LanceDB keeps
the previous versions for seven days, so `table.restore(<version>)` can undo a
run until then.

### 6. Run the application

```bash
# Terminal 1: backend (FastAPI dev server with reload, port 8000)
./scripts/run_backend.sh

# Terminal 2: frontend (Next.js with Turbopack, port 3000)
bun run dev
```

`./scripts/run_backend.sh` is `cd backend && uv run --env-file .env -- fastapi dev`.
Windows users can use the `.ps1` equivalents in `scripts/`.

- **Frontend:** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:8000](http://localhost:8000)
- **API documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

### 7. Production build

```bash
bun run build      # type-checks and builds the frontend
bun run start      # serves the build on port 3000
./scripts/run_backend_prod.sh
```

Both `dev` and `build` first copy the MapLibre worker into `public/maplibre/`.

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
- **similarity** (`packages/similarity/`): Compute per-species visual similarity from existing LanceDB embeddings and DuckDB metadata, then store the results in the `species_similarity` table.
- **morphospace** (`packages/morphospace/`): Precompute the dorso-ventral morphospaces of the UNICOM embeddings that the species, genus, and family pages draw. See [packages/morphospace/README.md](packages/morphospace/README.md).

Sync all packages first:

```bash
uv sync --all-packages
```

Run every command in this section from the repository root. The examples assume
the absolute path variables from [Configure the environment](#3-configure-the-environment)
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

To precompute similarity with existing embeddings and metadata (backend stopped):

```bash
uv run similarity run --db "$DUCK_DIR/biocosmos.duckdb" --lance-dir "$LANCE_DIR/biocosmos.lance"
```

See [packages/README.md](packages/README.md) and [reports/README.md](reports/README.md)
for the package details and generated artifact contract.

Everything in the root `tools/` directory is outdated and unused. Do not use those scripts for data preparation, embedding generation, or visualization setup.

## Testing

### Checks before a pull request

CI runs the backend and package suites on pull requests that touch `backend/`,
`packages/`, `pyproject.toml`, or `uv.lock`. There is no frontend test
harness, so run the build and lint for UI work and describe what you checked
by hand in the pull request.

**Backend** (always from `backend/`, which resolves `static/` relatively):

```bash
cd backend
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

**Packages** (100-character lines, Python 3.12):

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

**Frontend:**

```bash
bun run lint
bun run build
```

Ruff and ESLint already report findings on `main`, so compare against the
baseline and don't add new ones rather than expecting a clean run.

## Development Tips

### Backend Development

- **Hot reload:** `fastapi dev` (used by `run_backend.sh`) restarts on code changes. Startup reloads the ML models, so a restart takes a while.
- **API docs:** FastAPI generates interactive documentation at `/docs`.
- **Configuration:** everything except paths and secrets lives in `backend/app/configs/config.yaml`; LLM prompts are in `backend/app/configs/prompts/`.
- **Excluded families:** `image_meta` is a view that drops `image_metadata.exclude_families`. Always query `image_meta`, never `image_meta_source`.
- **Search index:** `search_index.build_vector` is `false`, so an ordinary start builds no vector index. Set it `true` for one boot after the embeddings are rebuilt, then back to `false`. Startup logs which path it took.
- **Dependencies:** add them to the right workspace member, e.g. `uv add --package backend <package>`, and commit the updated root `uv.lock`.
- **Agent planner:** after changing a planner prompt or tool argument model, re-export the spec (`cd backend && uv run python scripts/export_planner_spec.py`) and compare models with `plannerbench`; see [packages/plannerbench/README.md](packages/plannerbench/README.md).
- **Analyses:** `analyses/` is a separate uv project for the publication notebooks and index benchmarks; see [analyses/README.md](analyses/README.md). Its `lancedb` pin must match the root lockfile.

### Frontend Development

- **TypeScript:** strict mode; use the `@/` alias for imports from `src/`.
- **Tailwind CSS 4:** utility-first styling with the theme in `src/app/globals.css` and `tailwind.config.ts`.
- **Dark mode:** handled by `next-themes` with system preference detection.
- **API integration:** route handlers in `src/app/api/` proxy requests to the backend at `API_HOST`. They forward the backend's `Cache-Control`; see [Caching and Cache Invalidation](#caching-and-cache-invalidation).
- **Lint and format:** `bun run lint` runs ESLint and then `prettier --check`. `bun run format` formats the frontend with Prettier, and `bun run lint:fix` applies ESLint's fixable subset as well. `next lint` no longer exists in Next 16; the scripts call ESLint with `eslint.config.mjs`.

## Caching and Cache Invalidation

Responses are cached in several places, and some of those places cannot be
cleared from the server. Decide how a cached response will be retired
**before** you choose how long it may live.

### Where responses are cached

- **Browser and CDN (HTTP cache).** Set by the `Cache-Control` and `ETag`
  headers, which are defined in `backend/app/routers/http_cache.py` and
  forwarded by the proxies in `src/app/api/`. Entries last up to 30 days
  (higher-taxon overviews), or 1 day for similarity, literature and genetics.
  **The server cannot clear them.** They retire only by expiring, by an `ETag`
  mismatch on revalidation, or by the request URL changing.
- **Next.js data cache.** Set by `fetch(..., { next: { revalidate } })` in
  `src/lib/` (featured species, higher taxa, country diversity). Entries last
  for the `revalidate` value and are cleared by a frontend redeploy.
- **Backend in-process caches.** `TtlCache`
  (`backend/app/services/ttl_cache.py`) holds CrossRef and NCBI answers for a
  week, and `agent_cache.py` holds agent searches for 15 minutes. Restarting
  the backend empties them.
- **Precomputed DuckDB tables.** Built by
  `similarity run` and `geoharmonize integrate`, and
  kept until you rerun them.

### Choosing an invalidation mechanism

Use the first of these that fits:

1. **An `ETag` tied to the data's source.** When a payload is derived from an
   ingestion, build the `ETag` from the ingestion fingerprint, as
   `_overview_etag` in `backend/app/routers/species_data.py` does. A
   re-ingestion then changes every `ETag` at once, and a shared cache notices
   on its next revalidation.
2. **A payload version.** A fingerprint describes the inputs, not the code. When
   the same inputs start producing a different payload, bump a version:
   - When the endpoint already has an `ETag`, bump the version inside it
     (`OVERVIEW_PAYLOAD_VERSION` in `backend/app/query/higher_taxa.py`).
   - When there is no `ETag`, put the version in the request URL
     (`GENETICS_PAYLOAD_VERSION` in `src/lib/genetic.ts`, sent as `&v=`). The
     URL is the cache key, so a new URL misses every stale copy, including
     ones in visitors' browsers that nothing else can reach.
3. **A short `max-age` alone.** Use this when there is nothing to fingerprint and
   the payload shape is stable. An example is the precomputed similarity
   table, which is regenerated on its own schedule.

### When to bump a payload version

Bump the version, and add a one-line note beside the constant saying why, when
a change would make **new frontend code render an old cached payload wrongly
or incompletely**. That includes:

- adding a field the page renders (the genetics `nuclear` section is an
  example);
- removing or renaming a field;
- changing what a value means or how it is counted, even when its name and
  type stay the same;
- fixing a bug that put wrong data in cached responses.

You don't need to bump it for changes that leave the payload the same, such
as refactors, logging and performance work. Even when you bump, write the
frontend to tolerate the old shape during a rollout, with optional chaining
and defaults. The old frontend and new backend can be live at the same time.

### Rules for new endpoints

- Define each `Cache-Control` policy as a constant in `http_cache.py`, with a
  comment explaining the duration and how an entry is retired early. Build
  responses with `cached_json`.
- Never cache errors: send `NO_STORE` for 4xx and 5xx responses. A long-lived
  cached error cannot be cleared from the browser that holds it.
- Cache partial results briefly: 5 minutes, in both the HTTP header and any
  in-process cache (`TtlCache.set(..., ttl=...)`). Then a failed upstream call
  doesn't outlive an outage.
- Next.js proxies forward the backend's `Cache-Control` and default to
  `no-store`. Don't set a separate policy in the proxy, except for
  content-addressed resources that never change (image bytes by ID are
  `immutable`).
- Cache calls to external APIs (CrossRef, NCBI, GBIF) in the backend service
  client, not in the browser. Cache the assembled payload, bound the cache's
  size, share one in-flight request between concurrent callers, and stay
  within the provider's published rate limits. `crossref.py` and
  `genetics.py` show the pattern.

### Clearing caches by hand

- **In-process caches:** restart the backend.
- **Next.js data cache:** redeploy the frontend, or wait for `revalidate`.
- **CDN:** purge through the CDN provider if the site sits behind one.
- **Visitors' browsers:** these can't be cleared. Bump the payload version.

### Verifying caching behaviour

- Check the headers on both hops. Each should show the expected
  `Cache-Control` and, where one applies, an `ETag`:

  ```bash
  curl -sI "http://localhost:8000/species/Danaus%20plexippus/genetics"
  ```

  The Next.js proxies answer only `GET`, so ask for the headers of a real
  request rather than a `HEAD`:

  ```bash
  curl -s -D - -o /dev/null "http://localhost:3000/api/genetics?species=Danaus%20plexippus&v=2"
  ```

- In the browser's developer tools, a response marked "(disk cache)" or with
  a transfer size of 0 was served from cache. Test a payload change with the
  cache disabled, and then again with it enabled. The second pass shows what
  returning visitors will get.

## Deployment

### Docker Compose

`docker-compose.yml` builds both images and mounts the data directories from
`backend/` and `public/images` into the backend container. The backend
reserves an NVIDIA GPU; remove the `deploy` block to run it on CPU. Container
paths are set in the compose file, and `backend/.env` is read only for the
optional secrets (LLM, CrossRef, NCBI).

```bash
docker compose up --build      # build and run
docker compose up -d           # run in the background
docker compose down            # stop
```

### Podman / Docker (manual container runs)

Both images build with the **repository root** as the context: the backend
needs the workspace `pyproject.toml`, `uv.lock`, and `packages/`.

```bash
docker network create biocosmos

docker build -t biocosmos-backend -f backend/Dockerfile .
docker build -t biocosmos-frontend -f Dockerfile.frontend .

docker run -d \
  --name backend \
  --network biocosmos \
  -p 8000:8000 \
  --env-file ./backend/.env \
  -e DUCK_DIR=/app/duck_db \
  -e LANCE_DIR=/app/lance_db \
  -e IMAGE_DIR=/app/images \
  -e IMAGE_META_DIR=/app/data \
  -e GBIF_DIR=/app/data \
  -e COL_DIR=/app/data/col \
  -v ./backend/duck_db:/app/duck_db:Z \
  -v ./backend/lance_db_lite:/app/lance_db:Z \
  -v ./backend/data:/app/data:Z \
  -v /absolute/path/to/catalogue-of-life-col-dp:/app/data/col:ro \
  -v ./backend/static:/app/static:Z \
  -v ./public/images:/app/images:Z \
  biocosmos-backend

docker run -d \
  --name frontend \
  --network biocosmos \
  -p 3000:3000 \
  -e API_HOST=http://backend:8000 \
  biocosmos-frontend
```

The `-e` flags come after `--env-file`, so the container paths override the
host paths in `backend/.env`. In a container, set `col.cache_dir` in
`config.yaml` so the 3.6 GB Catalogue of Life index persists under `DUCK_DIR`
rather than the container's home directory.

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

Use American English spelling in code, comments, UI copy, and documentation.

### Frontend

- Two-space indentation, `PascalCase` for components and interfaces, `camelCase` for functions and variables, and Next.js route conventions such as `[speciesName]/page.tsx`.
- Format with Prettier (`bun run format`), and run `bun run lint` and `bun run build` before opening a pull request.

### Backend and packages

- Four-space indentation, `snake_case` modules and functions, and typed FastAPI/Pydantic interfaces.
- Keep route handlers thin; put reusable logic in `query/` or `services/`.
- Lint and format with [Ruff](https://github.com/astral-sh/ruff): `uv run ruff check .` and `uv run ruff format --check .` in `backend/`, and the same commands on `packages/` from the root.
- Add tests as `test_<feature>.py`, with shared fixtures in `backend/tests/conftest.py`.

We look forward to your contributions!
