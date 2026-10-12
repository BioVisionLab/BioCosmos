# Publication analyses and backend benchmarks

Publication notebooks read the backend databases and export figures with their
summary data. The index benchmark measures search performance on an isolated
copy of the image table. Both workflows leave the source databases unchanged.

## Layout

| Path                                                                | Contents                                                                   |
| ------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `notebooks/`                                                        | One notebook per publication figure                                        |
| `benchmarks/`                                                       | `image_indexing.ipynb` and its implementation, `lance_indexing.py`         |
| `helpers/publication.py`                                            | Configuration, database queries, aggregation, and plotting                 |
| `helpers/country_mapping.py`                                        | Country normalization                                                      |
| `helpers/grid_mapping.py`                                           | Equal-area grid maps                                                       |
| `helpers/planner.py`, `indexing.py`, `mimicry.py`, `morphospace.py` | Panels shared by a figure's own notebook and the combined figures          |
| `data/`                                                             | Mimicry pairs, basemap, and app screenshots ([provenance](data/README.md)) |
| `results/`                                                          | Generated figures and CSVs (gitignored)                                    |

Notebooks import helpers as `analyses.helpers.<module>`.

## Setup

`analyses/` is a standalone uv project with its own environment and lockfile.
Run these commands from the repository root:

```bash
env -u VIRTUAL_ENV uv sync --project analyses --locked
env -u VIRTUAL_ENV uv run --project analyses jupyter lab analyses/notebooks
```

`env -u VIRTUAL_ENV` removes the active environment setting for that command, so
uv uses `analyses/.venv`. Do not add `--active`, which would select the active
environment instead. Select the `analyses/.venv` kernel in Jupyter and run each
notebook from top to bottom. Add dependencies with
`uv add --project analyses <dependency>` to keep the project and lockfile in
sync.

## Prerequisites

- `DUCK_DIR` and `LANCE_DIR` come from `backend/.env` (existing environment
  variables take precedence). Database and table names come from
  `backend/app/configs/config.yaml`. Relative paths resolve from `backend/`.
- The backend must already have built the image metadata, GBIF, locality, and
  taxonomy tables. Build coordinate validation with `geoharmonize integrate` and
  morphospace tables with `morphospace run` followed by `morphospace integrate`.
- Stop the backend first, or point `DUCK_DIR` at an offline snapshot. The API
  holds DuckDB open read-write, preventing another process from attaching.
  Notebooks do not stop services or copy live databases.
- Missing tables or columns, empty populations, and duplicate keys raise errors.
  Resolve them before exporting figures.

## Figures

| Notebook                   | Figure                                                                                                                                                                                                                                |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data_summary.ipynb`       | `dataset_overview`: dorso-ventral (A), image providers (B), source aggregators (C), family (D), top ten accepted species (E), validated-coordinate grid (F), species richness by country (G), morphospace (H), rarefied disparity (I) |
| `harmonization.ipynb`      | `harmonization_metrics`: coordinate-validation outcomes and taxonomic match methods for images and unique input taxa                                                                                                                  |
| `index_performance.ipynb`  | `indexing_benchmark`: latest completed index run, latency against recall@10                                                                                                                                                           |
| `model_performance.ipynb`  | Planner accuracy against latency and tokens, and per-case accuracy                                                                                                                                                                    |
| `morphospace.ipynb`        | `morphospace`: species centroids on shared PCs (A) and rarefied disparity (B); also `morphospace_pca` and `morphospace_disparity` alone                                                                                               |
| `mimicry.ipynb`            | `mimicry_recovery`: partner ranks of the tested mimicry pairs with their matched images (A) and permutation tests (B)                                                                                                                 |
| `search_performance.ipynb` | `search_performance`: planner (A–C), mimicry pairs (D), and index (E) panels, drawn by the same helpers as their own notebooks                                                                                                        |
| `screenshot_bento.ipynb`   | A 2 × 2 composite of four app screenshots from `data/screenshots/`                                                                                                                                                                    |

## Methods and definitions

### Figure style

Colors use seaborn palettes, with ColorBrewer `Dark2` as the default in
`publication_style()`. Bars use one color because their categories are labeled.
Pies use a shared palette ordered from largest to smallest share; colors
indicate rank within a panel, not fixed categories across panels. Counts and
percentages appear in a legend beside each pie.

`category_plot()` uses a pie for exactly two classes covering the full
population and bars otherwise. Use `kind=` and `palette=` to override these
defaults. Pies reject `top` and `exclude` because their proportions must cover
the full population.

### Counting unit

Each unique, nonblank `img_id` counts once. Dorsal and ventral images of the
same specimen count separately, and per-image joins must be one-to-one.
Proportions include unknowns in the stated population. Top-ten percentages keep
the full denominator; they are not renormalized to the subset. Ties are sorted
alphabetically.

### Taxonomy

Accepted families and species come only from `MATCHED` records. Species use
`accepted_species_name`, falling back to `accepted_name` for species-rank
matches. Subspecies are grouped under their species, and genus-only matches are
excluded from species rankings. Ambiguous candidates do not contribute to
accepted-taxon counts. Matching panels include unresolved outcomes and count
either all images or all distinct referenced input-taxon keys.

All collection queries use the filtered `image_meta` view. If excluded families
change, restart the backend, rebuild similarity and morphospace, and rerun the
notebooks.

### Geography

- **Availability.** Recorded coordinates require two finite numbers.
  Out-of-range pairs and `(0, 0)` still count as available. Detailed locality
  requires a nonblank `locality` or `verbatim_locality`.
- **Validation.** Categories come from the coordinate-validation table. Images
  without a matching validation row are "Not evaluated."
- **Grid (panel F).** `VALID` coordinates fall into a 100 × 100 km EPSG:8857
  equal-area grid anchored at (0, 0), with lower bounds included. Cells count
  images on a log scale with no correction for sampling effort; gray land has no
  validated images. `dataset_overview_cells.csv` adds distinct accepted species
  and cell bounds.
- **Countries (panel G).** An image with an accepted species maps to a country
  when its coordinate falls in exactly one GADM region and nothing contradicts
  it: `COUNTRY_MATCH` (including `ADM1_MISMATCH`) or `COUNTRY_NOT_PROVIDED`,
  where the country is imputed from the coordinate. The `country_source` column
  and the printed count keep imputed countries distinguishable. Mismatched,
  ambiguous, and unmatched coordinates are excluded. GADM `GID_0` codes
  normalize to ISO alpha-2 by exact code or unambiguous name, never fuzzily.
  Read country CSVs with `keep_default_na=False` to preserve Namibia's `NA`
  code.
- **Map.** The Equal Earth basemap shades a polygon without its own ISO code
  with the country assigned by GADM (for example, Somaliland with Somalia).
  Territories without a 110m polygon get fixed-size markers on the same scale;
  marker positions are labels, not specimen locations. See
  [country marker reference](data/README.md).

### Providers and aggregators

- **Providers (panel B).** GBIF `institutionID` takes precedence over
  `institutionCode`. A code-only record joins an ID only when the code maps to
  one ID; otherwise it is "Conflicting attribution." Duplicate GBIF rows do not
  multiply counts. Providers outside the top five are grouped as "Other
  providers." URLs and names are not used to infer attribution.
- **Aggregators (panel C).** Counts recorded `source_db` keys using display
  names (`gbif` → GBIF, `scanbugs` → SCAN, `ecdysis` → Ecdysis). Combined keys
  such as `gbif/scanbugs` remain a single category; blank keys are "Unknown."

### Morphospace

Panels read one integrated morphospace run for `SCOPE_RANK` and `SCOPE_KEY`,
using the whole collection by default. The notebook prints the `run_id`. The PCA
panel shows species centroids with filled dorsal points and hollow ventral
points, family mean positions, and the site's representative images at the axis
ends. Missing images raise an error. The disparity panel shows the rarefied sum
of species-centroid variances with 95% intervals; sides with too few species are
marked N/A. See the [morphospace package](../packages/morphospace/README.md).

### Mimicry recovery

This analysis tests whether visual similarity ranks the published pairs in
`data/mimicry_pairs.csv` near each other. It reads LanceDB; run it with the
backend stopped.

- **Test.** Dorsal against dorsal: each species' dorsal UNICOM centroid queries
  the dorsal images of every species, and each candidate is scored by its
  nearest image, as in `similarity run`. Ventral images are not used. Ranks
  differ from the site's list, which scores both sides.
- **Species.** Species follow the accepted-name rules in [Taxonomy](#taxonomy).
  A published name that is not accepted resolves through its images when they
  agree on one species (_Adelpha bredowii_ → _Limenitis bredowii_). Only pairs
  with dorsal images of both species are tested; the notebook lists excluded
  pairs, which should agree with the CSV's `Availability` column.
- **Statistic.** Mean partner percentile over both directions (1 = nearest, 0.5
  = chance), against three nulls: **Random** partners, **Query congeners** for
  congeneric pairs, and **Partner congeners**. With 10,000 permutations, the
  minimum p-value is 1/10,001. `pair_tests` reports exact per-pair results;
  `leave_one_out` drops pairs sharing a species.
- **Mutual top 10.** Highlighted pairs where each species is in the other's top
  ten. Each pair shows the image used to score each species and its dorsal image
  count, N.

### Planner models

`model_performance.ipynb` compares models within one `plannerbench` run, from
`reports/latest.json` or `BIOCOSMOS_PLANNER_MANIFEST`. Cost panels highlight
Pareto leaders. Models with no successful calls are flagged as access or
provider failures. They remain in the heatmap and are excluded from rankings.

```bash
uv sync --all-packages --locked
cd backend
uv run python scripts/export_planner_spec.py
cd ..
uv run --env-file backend/.env plannerbench run \
    -m mistral-small-3.1 \
    -m gemma-4-31b-it \
    -m gpt-oss-20b \
    -m meta-muse-glimmer-30b \
    -m nemotron-3-nano-30b-a3b \
    --repeats 5
```

## Index benchmark

`benchmarks/image_indexing.ipynb` compares exact search, IVF-PQ, IVF-HNSW-SQ,
and IVF-HNSW-PQ for the UNICOM and CLIP columns, using the backend's cosine
metric.

```bash
env -u VIRTUAL_ENV uv sync --project analyses --extra indexing --locked
env -u VIRTUAL_ENV uv run --project analyses --extra indexing jupyter lab analyses/benchmarks/image_indexing.ipynb
```

- **Dependencies.** The `indexing` extra pins LanceDB `0.39.0` to match the
  backend; keep it aligned.
- **Parameters.** Configuration cells set sample size, repetitions, warmup,
  partitions, and PQ subvectors. Subvectors must divide the embedding dimension;
  training needs at least 256 rows and as many rows as partitions.
- **Isolation.** Each run copies a fixed source version to
  `results/indexing/<timestamp_uuid>/scratch.lance` and indexes only that copy.
  Allow enough disk space for the copy and indexes. Runs are retained and
  gitignored.
- **Outputs.** `indexing_benchmark.csv`, `query_timings.csv`,
  `recommendations.csv`, and `run.json`. Recall@k is against exact top-k by
  image ID. Queries per second (QPS) measure sequential search and exclude HTTP
  overhead and model inference. Cold caches and training randomness are not
  controlled. Recommendations are saved for review; they are not applied.

`index_performance.ipynb` plots the newest completed run at top-k 10, excluding
`Flat (brute-force)` and keeping `No Index (baseline)`.

## Exports

Each figure exports a PDF, an SVG with editable text, a 300-dpi PNG, and summary
CSVs to `analyses/results/`. Outputs replace existing files with the same names.
CSVs retain counts, unrounded percentages, and denominators; figure labels round
percentages to one decimal place. Set `BIOCOSMOS_ANALYSES_OUTPUT` to use another
directory within `analyses/`.

Inspect the exports before publication, especially institution labels and large
unresolved categories.

## Development

```bash
uv run --project analyses ruff check analyses
uv run --project analyses ruff format --check analyses
```
