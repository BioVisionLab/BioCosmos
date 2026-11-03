# BioCosmos Packages

Seven Python packages for taxonomic/geographic harmonization, institution resolution, precomputed morphological analyses, and LLM planner benchmarking. All seven belong to the root `uv` workspace alongside `backend/` and share the root `uv.lock`.

| Package | CLI command | Purpose |
| :--- | :--- | :--- |
| [`harmonize-core`](harmonize-core/README.md) | — | Shared DuckDB access, TOML configuration, country/place normalization, and artifact reporting |
| [`colharmonize`](colharmonize/README.md) | `colharmonize` | Match occurrence scientific names against a Catalogue of Life release |
| [`geoharmonize`](geoharmonize/README.md) | `geoharmonize` | Validate occurrence coordinates against GADM administrative boundaries |
| [`instharmonize`](instharmonize/README.md) | `instharmonize` | Resolve institution codes to names and websites via GBIF GRSciColl |
| [`morphospace`](morphospace/README.md) | `morphospace` | Precompute dorso-ventral PCA morphospaces, disparity, and Mantel correlations from UNICOM embeddings |
| [`similarity`](similarity/README.md) | `similarity` | Precompute the visually similar species displayed on species pages |
| [`plannerbench`](plannerbench/README.md) | `plannerbench` | Benchmark language models on the production agent-search planner prompt |

`colharmonize`, `geoharmonize`, and `harmonize-core` originated in [col-taxonomy](https://github.com/hhandika/col-taxonomy) and share common infrastructure while keeping their domain logic separate.

## Setup

Run all package commands from the repository root (Python 3.12+):

```bash
uv sync --all-packages

uv run colharmonize --help
uv run geoharmonize --help
```

Commands that reference `$DUCK_DIR`, `$LANCE_DIR`, `$COL_DIR`, or `$GADM_DIR` assume those variables are exported in your shell (see [Configure the environment](../CONTRIBUTING.md#3-configure-the-environment)).

> **Stop the backend before accessing the live DuckDB file.** DuckDB allows only a single writer, and the running FastAPI service holds `biocosmos.duckdb` open read-write, preventing any CLI tool from attaching even in read-only mode.

## How the Backend Uses These Packages

None of the packages import `backend/`. Instead, the backend either imports a package at startup or reads the tables produced by an offline CLI run:

- **Run automatically at backend startup**:
  - `colharmonize`: Matches recorded names in `image_meta_input` against Catalogue of Life and builds `image_meta_taxonomy` and `image_meta_excluded`. Its CLI is only needed when tuning parameters or exporting standalone CSV/plot reports.
  - `instharmonize`: Resolves collection codes via GBIF and caches institution names and homepages in `institution_directory`.
- **Run offline with the backend stopped**:
  - `geoharmonize integrate`: Reads `main.image_meta_locality` (built by the backend at startup) and writes `main.image_meta_coordinates`.
  - `morphospace run` & `morphospace integrate`: Computes dorso-ventral PCA morphospaces under `reports/morphospace/<run_id>/` and copies the five `morphospace_*` tables into `biocosmos.duckdb`.
  - `similarity run`: Computes per-species visual neighbors and writes `species_similarity` directly into `biocosmos.duckdb`.
- **Run against an LLM endpoint (no database required)**:
  - `plannerbench`: Reads `reports/planner/planner_spec.json` (exported by `backend/scripts/export_planner_spec.py`) and grades candidate LLMs.

All collection readers query the filtered `image_meta` view. Whenever you change `image_metadata.exclude_families`, `col.family_synonyms`, or `col.taxon_overrides` in `backend/app/configs/config.yaml`, restart the backend first, stop it, and then re-run `similarity run`, `morphospace run`/`integrate`, and the notebooks in [`analyses/`](../analyses/README.md).

Run artifacts for taxonomy, geography, morphospace, and planner benchmarks are written to [`reports/`](../reports/README.md) (gitignored).

## Development and Testing

```bash
uv run --package harmonize-core pytest packages/harmonize-core/tests -q
uv run --package colharmonize pytest packages/colharmonize/tests -q
uv run --package geoharmonize pytest packages/geoharmonize/tests -q
uv run --package instharmonize pytest packages/instharmonize/tests -q
uv run --package morphospace pytest packages/morphospace/tests -q
uv run --package similarity pytest packages/similarity/tests -q
uv run --package plannerbench pytest packages/plannerbench/tests -q

uv run ruff check packages/
uv run ruff format --check packages/
```
