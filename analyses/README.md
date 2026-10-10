# Publication analyses and backend benchmarks

Notebooks in `notebooks/` load summaries from the backend databases, draw one publication
figure each, and export it. `benchmarks/` tests vector-index performance on an isolated copy
of the image table. Neither changes a backend source database.

## Layout

| Path | Contents |
| --- | --- |
| `notebooks/` | One notebook per publication figure |
| `benchmarks/` | `image_indexing.ipynb` and its implementation, `lance_indexing.py` |
| `helpers/publication.py` | Configuration, database queries, aggregation, and plotting |
| `helpers/country_mapping.py` | Country normalization |
| `helpers/grid_mapping.py` | Equal-area grid maps |
| `helpers/planner.py`, `indexing.py`, `mimicry.py`, `morphospace.py` | Panels shared by a figure's own notebook and the combined figures |
| `data/` | Mimicry pairs, basemap, and app screenshots ([provenance](data/README.md)) |
| `results/` | Generated figures and CSVs (gitignored) |

Notebooks import helpers as `analyses.helpers.<module>`.

## Setup

This is a standalone uv project, so its environment and lockfile never touch the backend or
the root workspace. From the repository root:

```bash
env -u VIRTUAL_ENV uv sync --project analyses --locked
env -u VIRTUAL_ENV uv run --project analyses jupyter lab analyses/notebooks
```

`env -u VIRTUAL_ENV` drops an active backend environment for that command only, so uv uses
`analyses/.venv`; ignore the environment-mismatch warning and do not add `--active`. Select
the `analyses/.venv` kernel and run notebooks top to bottom. Add dependencies with
`uv add --project analyses <dependency>`; do not use pip or a requirements file.

## Prerequisites

- `DUCK_DIR` and `LANCE_DIR` come from `backend/.env` (an existing environment variable
  wins). Database and table names come from `backend/app/configs/config.yaml`. Relative paths
  resolve from `backend/`.
- The backend must already have built the image metadata, GBIF, locality, and taxonomy
  tables. Coordinate validation comes from `geoharmonize integrate`, the morphospace tables
  from `morphospace integrate`.
- Stop the backend first, or point `DUCK_DIR` at an offline snapshot: DuckDB allows a single
  writer. Notebooks never stop services or copy a live database.
- Missing tables or columns, empty populations, and duplicate keys raise errors rather than
  producing misleading figures.

## Figures

| Notebook | Figure |
| --- | --- |
| `data_summary.ipynb` | `dataset_overview`: dorso-ventral (A), image providers (B), source aggregators (C), family (D), top ten accepted species (E), validated-coordinate grid (F), species richness by country (G), morphospace (H), rarefied disparity (I) |
| `harmonization.ipynb` | `harmonization_metrics`: coordinate-validation outcomes and taxonomic match methods for images and unique input taxa |
| `index_performance.ipynb` | `indexing_benchmark`: latest completed index run, latency against recall@10 |
| `model_performance.ipynb` | Planner accuracy against latency and tokens, and per-case accuracy |
| `morphospace.ipynb` | `morphospace`: species centroids on shared PCs (A) and rarefied disparity (B); also `morphospace_pca` and `morphospace_disparity` alone |
| `mimicry.ipynb` | `mimicry_recovery`: partner ranks of the tested mimicry pairs with their matched images (A) and permutation tests (B) |
| `search_performance.ipynb` | `search_performance`: planner (A–C), mimicry pairs (D), and index (E) panels, drawn by the same helpers as their own notebooks |
| `screenshot_bento.ipynb` | A 2 × 2 composite of four app screenshots from `data/screenshots/` |

## Definitions

### Figure style

Colors come from seaborn, defaulting to ColorBrewer `Dark2` via `publication_style()`. Bars
use one color, since each bar is already a labeled category. Pies share one palette ordered
largest share first, so a color follows rank within its panel, not a fixed meaning; counts and
percentages sit in a legend beside the pie. `category_plot()` draws a pie for exactly two
classes of a complete population and bars otherwise; `kind=` and `palette=` override this.
Pies never take `top`/`exclude`, because a ranked subset is not a whole.

### Counting unit

Each unique nonblank `img_id` counts once; dorsal and ventral images of one specimen stay
separate. Per-image joins must be one-to-one. Proportions use the full stated population,
including unknowns, and top-ten percentages are not renormalized. Ties sort alphabetically.

### Taxonomy

Only `MATCHED` records supply accepted families and species. Species use
`accepted_species_name`, falling back to `accepted_name` at species rank, so subspecies group
under their species and genus-only matches are excluded from species rankings. Ambiguous
candidates never count. Matching panels count all images, or all distinct referenced
input-taxon keys, including unresolved outcomes.

### Geography

- **Availability.** Coordinates need two finite numbers; out-of-range pairs and `(0, 0)` still
  count as recorded. Detailed locality needs a nonblank `locality` or `verbatim_locality`.
- **Validation.** Categories come straight from the coordinate-validation table; unjoined
  images are "Not evaluated."
- **Grid (panel F).** `VALID` coordinates fall into a 100 × 100 km EPSG:8857 equal-area grid
  anchored at (0, 0), lower-inclusive. Cells count images on a log scale with no correction
  for sampling effort; gray land has no validated images. `dataset_overview_cells.csv` adds
  distinct accepted species and cell bounds.
- **Countries (panel G).** An image with an accepted species maps to a country when its
  coordinate falls in exactly one GADM region and nothing contradicts it: `COUNTRY_MATCH`
  (including `ADM1_MISMATCH`) or `COUNTRY_NOT_PROVIDED`, where the country is imputed from
  the coordinate. The `country_source` column and the printed count keep imputed countries
  distinguishable. Mismatched, ambiguous, and unmatched coordinates are excluded. GADM
  `GID_0` codes normalize to ISO alpha-2 by exact code or unambiguous name, never fuzzily.
  Read the country CSVs with `keep_default_na=False` to keep Namibia's `NA`.
- **Map.** The Equal Earth basemap shades a polygon without its own ISO code with the
  country GADM files it under (Somaliland with Somalia). Territories without a 110m polygon
  get fixed-size markers on the same scale; marker positions are labels, not specimen
  locations. See [country marker reference](data/README.md).

### Providers and aggregators

- **Providers (panel B).** GBIF `institutionID` takes precedence over `institutionCode`. A
  code-only record joins an ID only when the code maps to one ID; otherwise it is
  "Conflicting attribution." Duplicate GBIF rows do not multiply counts. Providers past the
  top five pool as "Other providers." Nothing is inferred from URLs or names.
- **Aggregators (panel C).** Counts the recorded `source_db` key in published form (`gbif` →
  GBIF, `scanbugs` → SCAN, `ecdysis` → Ecdysis). Combined keys such as `gbif/scanbugs` stay
  one category; blank keys are "Unknown."

### Morphospace

Panels read one integrated `morphospace run`, whose `run_id` the notebook prints, for
`SCOPE_RANK`/`SCOPE_KEY` (the whole collection by default). The PCA panel shows species
centroids, dorsal filled and ventral hollow, with each family's mean positions and the
site's representative images at the axis ends; missing images raise an error. The disparity
panel shows the rarefied sum of species-centroid variances with 95% intervals; a side with
too few species is N/A. See [`packages/morphospace`](../packages/morphospace/README.md).

### Mimicry recovery

Asks whether visual similarity places the published pairs in `data/mimicry_pairs.csv` near
each other. Reads LanceDB, so run it with the backend stopped.

- **Test.** Dorsal against dorsal: each species' dorsal UNICOM centroid queries the dorsal
  images of every species, and each candidate scores its nearest image, as `similarity run`
  does. Ventral images are not used. Ranks differ from the site's list, which scores both
  sides.
- **Species.** Accepted names as in [Taxonomy](#taxonomy). A published name that is not
  accepted resolves through its images when they agree on one species (*Adelpha bredowii* →
  *Limenitis bredowii*). Only pairs with dorsal images of both species are tested; the
  notebook prints the rest, and the `Availability` column should match.
- **Statistic.** Mean partner percentile over both directions (1 = nearest, 0.5 = chance),
  against three nulls: **Random** partners, **Query congeners** for congeneric pairs, and
  **Partner congeners**. With 10,000 permutations, p ≥ 1/10,001. `pair_tests` gives exact
  per-pair results, and `leave_one_out` drops pairs sharing a species.
- **Mutual top 10.** Highlighted pairs where each species is in the other's top ten. Each
  pair shows the image that sets each species' score, with its dorsal image count N.

### Planner models

`model_performance.ipynb` compares models within one `plannerbench` run, from
`reports/latest.json` or `BIOCOSMOS_PLANNER_MANIFEST`. Cost panels highlight Pareto leaders.
Models with no successful calls are flagged as access or provider failures, kept in the
heatmap, and never ranked.

```bash
uv sync --all-packages --locked
cd backend && uv run scripts/export_planner_spec.py && cd ..
uv run --env-file backend/.env plannerbench run \
    -m mistral-small-3.1 \
    -m gemma-4-31b-it \
    -m gpt-oss-20b \
    -m meta-muse-glimmer-30b \
    -m nemotron-3-nano-30b-a3b \
    --repeats 5
```

## Index benchmark

`benchmarks/image_indexing.ipynb` compares exact search, IVF-PQ, IVF-HNSW-SQ, and
IVF-HNSW-PQ for the UNICOM and CLIP columns, using the backend's cosine metric.

```bash
env -u VIRTUAL_ENV uv sync --project analyses --extra indexing --locked
env -u VIRTUAL_ENV uv run --project analyses --extra indexing jupyter lab analyses/benchmarks/image_indexing.ipynb
```

- **Pin.** The `indexing` extra pins LanceDB `0.39.0` to match the backend; keep it aligned.
- **Parameters.** Configuration cells set sample size, repetitions, warmup, partitions, and
  PQ subvectors. Subvectors must divide the embedding dimension; training needs at least 256
  rows and as many rows as partitions.
- **Isolation.** Each run copies a pinned source version to
  `results/indexing/<timestamp_uuid>/scratch.lance` and indexes only that copy. Allow disk
  space; runs are kept and gitignored.
- **Outputs.** `indexing_benchmark.csv`, `query_timings.csv`, `recommendations.csv`, and
  `run.json`. Recall@k is against exact top-k by image ID. QPS is sequential and excludes
  HTTP and inference; cold caches and training randomness are not controlled.
  Recommendations are advisory and never deployed.

`index_performance.ipynb` plots the newest completed run (top-k 10), excluding
`Flat (brute-force)` and keeping `No Index (baseline)`.

## Exports

Each figure exports PDF, SVG (editable text), 300-dpi PNG, and its summary CSVs to
`analyses/results/`, replacing earlier outputs of the same name. CSVs keep counts,
unrounded percentages, and denominators; displayed percentages round to one decimal.
`BIOCOSMOS_ANALYSES_OUTPUT` picks another directory within `analyses/`. Inspect exports
before publication, especially institution labels and large unresolved categories.

```bash
uv run --project analyses ruff check analyses
uv run --project analyses ruff format --check analyses
```
