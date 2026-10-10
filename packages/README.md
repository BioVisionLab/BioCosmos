# BioCosmos packages

Python packages for data harmonization, precomputed image analyses, and
agent-search benchmarks. All seven packages belong to the root uv workspace
alongside `backend/`, with one environment and one lockfile.

| Package                                      | Command         | Purpose                                                                               |
| -------------------------------------------- | --------------- | ------------------------------------------------------------------------------------- |
| [`harmonize-core`](harmonize-core/README.md) | —               | Shared DuckDB access, configuration, country mapping, and reporting                   |
| [`colharmonize`](colharmonize/README.md)     | `colharmonize`  | Match occurrence names against a Catalogue of Life release                            |
| [`geoharmonize`](geoharmonize/README.md)     | `geoharmonize`  | Validate occurrence coordinates against GADM geography                                |
| [`instharmonize`](instharmonize/README.md)   | `instharmonize` | Resolve institution codes to names and websites through GBIF                          |
| [`morphospace`](morphospace/README.md)       | `morphospace`   | Compute dorso-ventral morphospaces, disparity, and correlation from UNICOM embeddings |
| [`similarity`](similarity/README.md)         | `similarity`    | Precompute the visually similar species shown on species pages                        |
| [`plannerbench`](plannerbench/README.md)     | `plannerbench`  | Compare language models using the production agent-search planner request             |

The taxonomy and geography tools came from
[col-taxonomy](https://github.com/hhandika/col-taxonomy), imported with its
history. They share infrastructure through `harmonize-core`, but keep their
domain logic and dependencies separate.

## Setup

Run package commands from the repository root. Python 3.12 or later is required.

```bash
uv sync --all-packages

uv run colharmonize --help
uv run geoharmonize --help
```

Commands that use `$DUCK_DIR`, `$LANCE_DIR`, or other path variables assume
those variables are exported in your shell. See the
[environment setup](../CONTRIBUTING.md#3-configure-the-environment).

Stop the backend before opening its live DuckDB file with a package command,
even for a read-only operation. The API holds the file open read-write, which
prevents another process from attaching to it. An offline snapshot can be read
separately.

## How the backend uses the packages

The packages do not import the backend. The backend imports `colharmonize` and
`instharmonize` and runs them at startup:

- `colharmonize` matches the collection's taxonomy and writes the application
  tables. Its CLI is useful for tuning and report exports, but is not required
  to start the site.
- `instharmonize` resolves institution codes and stores names and websites in
  `institution_directory`. It queries GBIF for codes without a cached result.

Other workflows run offline:

- After the backend builds `main.image_meta_locality`, `geoharmonize integrate`
  writes `main.image_meta_coordinates` for the backend to read.
- `morphospace run` computes a run artifact; `morphospace integrate` copies its
  tables into the backend database.
- `similarity run` writes `species_similarity` directly into the backend
  database.
- `plannerbench` reads the spec exported by
  `backend/scripts/export_planner_spec.py`. It needs an LLM endpoint, but no
  database or running backend.

Collection readers use the filtered `image_meta` view. After changing
`image_metadata.exclude_families`, restart the backend, then rebuild similarity,
run and integrate morphospace, and rerun the publication notebooks.

Taxonomy, geography, morphospace, and planner runs save their artifacts under
[`reports/`](../reports/README.md). Generated reports are gitignored.

## Development

Run the suite for the package you changed, or all seven when changing shared
behavior:

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
