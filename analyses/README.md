# Publication analyses and backend benchmarks

Jupyter notebook files in `notebooks/` load summaries, draw figures, and export them.
Each notebook produces exactly one publication figure; intermediate exploratory panels
are not kept.
Reusable helpers live in the `helpers/` package: configuration, database queries and
aggregation, and matplotlib/seaborn plotting in `helpers/publication.py`; country
normalization in `helpers/country_mapping.py`; and the equal-area grid maps in
`helpers/grid_mapping.py`. Notebooks import them as `analyses.helpers.<module>`.

The separate `benchmarks/` workflow tests backend vector-index performance on an isolated copy.
Neither workflow changes a backend source database.

## Indexing and backend performance

`benchmarks/image_indexing.ipynb` is to test the performance of the backend vector-index on an isolated copy of the database.
Its implementation lives in `benchmarks/lance_indexing.py`.

From the repository root, use these complete shell commands. `env -u VIRTUAL_ENV`
removes an active backend environment for that command only; uv then uses
`analyses/.venv`. The environment-mismatch warning does not mean the install
failed. Do not add `--active`, which would target the backend environment.

```bash
env -u VIRTUAL_ENV uv sync --project analyses --extra indexing --locked
env -u VIRTUAL_ENV uv run --project analyses --extra indexing jupyter lab analyses/benchmarks/image_indexing.ipynb
```

The optional indexing dependencies pin LanceDB to `0.39.0`, matching the backend's
current root lockfile. Keep this pin aligned when upgrading the backend. `LANCE_DIR`
comes from `backend/.env`. The database filename and image table name come
from backend YAML config file (`backend/app/configs/config.yaml`). Relative paths resolve from
`backend/`.

Run setup/configuration cells first to inspect the source and select sample size,
repetitions, warmup, partitions, PQ subvectors, and optional query controls. Defaults
test UNICOM and CLIP against exact search, IVF-PQ, IVF-HNSW-SQ, and IVF-HNSW-PQ.
The same seeded sample across the full table is used for each candidate. Both the
exact reference and ANN searches explicitly use the backend's cosine metric.
Subvector counts must divide embedding dimensions. ANN training requires at least
256 rows and at least as many rows as partitions. Missing/invalid vectors and duplicate
image IDs raise errors, rather than silently changing the benchmark population.

Running the benchmark streams a pinned source version into a new full-table copy
under `results/indexing/<timestamp_uuid>/scratch.lance`. Allow disk space for that
copy and its indexes. Only scratch indexes are created/replaced; existing backend
indexes stay intact. Avoid removing source versions while the copy is being read.
Scratch runs are retained, never automatically deleted, and are gitignored.

Each run exports `indexing_benchmark.csv`, `query_timings.csv`, `recommendations.csv`,
and `run.json` (source version, dimensions, sampled image IDs, parameters, library
version, and completion/failure status). Failed runs retain completed measurements
but are not complete experiments. Build time is separate from query latency. Recall
uses stable image IDs against exact cosine top-k results, with self matches included.
Latency percentiles include all timed repetitions after warmup; QPS describes
sequential queries, not concurrent backend throughput. This measures materialized
vector retrieval on a copy, excluding HTTP, inference, and backend response processing.
Cold-cache behavior and index-training randomness are not controlled.

Recommendations are advisory and respect the recall threshold per embedding column;
the notebook never deploys a winner. No figures are generated and the curated
`data/indexing_benchmark.csv` is never overwritten. The publication `index_perf.ipynb`
continues to plot that separate CSV; explicitly curate a completed benchmark export
into it if you want to update the publication's measurements (keep top-k at 10).

## Planner model performance

`benchmarks/planner_model_performance.ipynb` compares the models recorded by one
`plannerbench` run. It loads the planner entry in `reports/latest.json` by default,
or the manifest selected by `BIOCOSMOS_PLANNER_MANIFEST`. The notebook compares
accuracy, repeat consistency, latency, API/tool-call failures, prompt/completion/total
tokens, and per-case accuracy. Trial-level box plots expose latency and token outliers.
The quality-cost figure compares accuracy with p50 successful-call latency and tokens
per successful call. Each panel highlights its own Pareto leaders: models for which no
other eligible model is at least as accurate and no more costly, with a strict improvement
in at least one dimension. Models without successful calls or finite cost measurements
remain visible in the aggregate summary but are excluded from that comparison.
After the per-case section, a combined publication figure places accuracy versus latency
and token usage above the per-case accuracy heatmap. Every planner figure is exported as
PDF, SVG, and 300-dpi PNG, with its source CSV data, under `analyses/results/`.

Generate a run before opening the notebook. From the repository root,
install the workspace packages into the root `.venv`, activate it, and load
the provider settings from `backend/.env` into the current bash shell.
The last line of the `plannerbench` command has no trailing backslash.

```bash
uv sync --all-packages --locked

cd backend && uv run scripts/export_planner_spec.py
cd ..
# Compare models on the UF endpoint
uv run --env-file backend/.env plannerbench run \
    -m mistral-small-3.1 \
    -m gemma-4-31b-it \
    -m gpt-oss-20b \
    -m meta-muse-glimmer-30b \
    -m nemotron-3-nano-30b-a3b \
    --repeats 5
```

The activated root `.venv` supplies `plannerbench`; the separate
`analyses/.venv` supplies Jupyter. Run `deactivate` when finished.

Models are compared only within the selected run, where the prompt fingerprint,
cases, repeats, concurrency, and endpoint conditions are shared. The notebook is
read-only and never changes the backend model or benchmark artifacts. Models with
no successful calls are flagged as access/provider failures and must not be ranked
as though their zero accuracy measured model quality.

Indexing tests are optional with the dependency extra:

```bash
uv run --project analyses --extra indexing pytest analyses/tests -q
```

## Run with uv

This directory is a standalone uv project so its dependencies, lockfile, and environment
do not change the backend or root workspace. From the repository root:

```bash
env -u VIRTUAL_ENV uv sync --project analyses --locked
env -u VIRTUAL_ENV uv run --project analyses jupyter lab analyses/notebooks
```

Select the Python kernel from `analyses/.venv` and run a notebook from top to bottom.
The notebooks locate the repository from either its root, `analyses`, or `analyses/notebooks`.
For updates, use `uv add --project analyses <dependency>` and retain `analyses/uv.lock`.
The local `harmonize-core` package supplies SQL identifier handling; installing it does not
run its pipelines. Do not use pip or maintain a second requirements file.

## Input configuration and prerequisites

- Load `DUCK_DIR` from `backend/.env`; an existing environment variable takes precedence.
  The database filename and table names come from `backend/app/configs/config.yaml`.
  Relative input directories resolve from `backend/`, matching a backend launched there.
  Neither configuration is edited or printed, and backend startup code is not imported.
- The backend must already have prepared image metadata, GBIF, locality, and taxonomy tables.
  Coordinate validation must already exist from `geoharmonize integrate`.
- DuckDB must be readable. Stop the backend before opening a database it holds for writing,
  or set `DUCK_DIR` to an existing offline snapshot. Notebooks never stop services or copy
  a live database. Missing tables/columns, empty populations, or duplicate primary keys
  raise explicit errors instead of producing misleading figures.
- Raw metadata, CoL, GBIF source files, and GADM are not needed once these tables exist.

## Figures and definitions

| Notebook | Figure |
| --- | --- |
| `data_summary.ipynb` | `dataset_overview`: dorso-ventral (A), image providers (B), source aggregators (C), family (D), top ten accepted species (E), validated-coordinate grid (F), species diversity by validated country (G) |
| `harmonization.ipynb` | `harmonization_metrics`: coordinate-validation outcomes and match methods for images and unique input taxa |
| `index_perf.ipynb` | `indexing_benchmark`: recorded index latency versus recall@10 |

**Figure style.** Colours come from seaborn, defaulting to the ColorBrewer `Dark2`
qualitative palette set by `publication_style()`. Bars are one colour: each bar is a labelled
category, so per-bar colour would imply a grouping that is not there. Every pie uses the same
palette in the same order, largest share first, so the figures read as one set; a category's
colour therefore follows its rank within its own panel, not a fixed meaning. `category_plot()`
draws a pie when a summary compares exactly two classes of a complete population and bars
otherwise; pass `kind="pie"` for a whole-population panel worth reading as shares even with more
than two classes (match status does this), `kind="bar"` to force bars, and `palette=` for another
seaborn palette. Pies never take `top`/`exclude`, because a ranked subset is not a whole. Pie counts and
percentages sit in a legend to the right of the pie rather than beside each wedge, so small
adjacent wedges cannot overlap and the legend fills the space an equal-aspect pie leaves in
its grid cell.

**Counting unit.** Each unique nonblank `img_id` counts once. Repeated specimen UUIDs are
expected: dorsal and ventral images remain separate. Prepared per-image joins must be
one-to-one; duplicate keys are rejected. Proportions include unresolved/unknown categories
and always use the full stated population. Top-ten percentages are not renormalized.
Rank ties use category labels alphabetically. Full distributions accompany rankings as CSV.

**Taxonomy used for composition.** Only `MATCHED` records supply accepted families and
species. Species use `accepted_species_name`, falling back to `accepted_name` only at
species rank. This groups subspecies where an accepted species exists and excludes
genus-only/unresolved assignments from the species ranking. Ambiguous candidates never
count as accepted identifications. Unresolved families remain a visible category.

**Country richness and mapping (panel G).** Countries come from the backend
coordinate-validation table written by `geoharmonize integrate`, not from raw locality
fields. An image (with `MATCHED` taxonomy to an accepted species) is mapped when its
coordinate falls in exactly one GADM region and nothing contradicts that region's country:
`COUNTRY_MATCH` (including `ADM1_MISMATCH` records, whose country is still validated even
though their state or province is not) or `COUNTRY_NOT_PROVIDED`, where no country was
recorded and the single GADM region stands unopposed — the country is **imputed from the
coordinate**. Those images carry a mapped coordinate, so dropping them would blank a country
here whose images appear in panel F. The exported audit carries a `country_source` column
(`validated against recorded country` or `imputed from coordinates`) for every group, and
the notebook prints the imputed image count, so an imputed country is never read as one the
collector recorded.
`COUNTRY_MISMATCH`, `NO_REFERENCE_MATCH`, `AMBIGUOUS_REFERENCE` and unevaluated
coordinates are never eligible. The GADM `GID_0` code is normalized to ISO alpha-2 before
counting distinct accepted species; non-ISO GADM codes (for example `XKO`, or the `Z0x`
disputed areas) resolve only through their exact, unambiguous GADM country name. There is
no fuzzy matching; anything else stays unresolved. The notebook displays the complete
GADM-reference-to-normalized audit (`reference_code`, `reference_country`) and exports
`dataset_overview_country_mapping.csv`; its per-reference species counts are not additive. `dataset_overview_country_species.csv` contains the deduplicated
country totals, with an empty code for the pooled unresolved group. Read these CSVs with
`keep_default_na=False` to preserve Namibia's literal `NA` code.

The Equal Earth map uses both Natural Earth code fields (including `TW` for Taiwan).
A basemap polygon with no ISO code of its own is shaded with the country GADM files its
territory under, so it does not read as having no records: Somaliland is drawn with
Somalia's total, which already includes those coordinates. It is not a separate total.
N. Cyprus stays unmapped, because no eligible record resolves to it.
Countries/territories lacking separate 110m polygons use fixed-size markers on the same
richness color scale; territories are never merged with parent-country totals. Marker
positions are representative labels, not specimen locations. The coarse basemap may
include overseas outlines in parent features; markers give those territories' own counts.
See [country lookup provenance](data/README.md) for the offline marker reference.

**Combined overview.** `dataset_overview` reads in three rows: dorso-ventral composition
(A), image providers (B) and source aggregators (C); family composition (D) and the top ten
accepted species (E); validated-coordinate image counts per grid cell (F) and species
richness by validated country (G). Panel B covers every image: providers after the top five
pool as “Other providers” and unattributed/conflicting images pool separately, both in gray;
institution codes keep their recorded capitalization. `top_share()` builds that frame, and
the pie exports as `dataset_overview_provider_shares.csv` beside the grid cells and country
tables.

**Source aggregators.** Panel C counts the recorded `source_db` key on each image. Keys
print in published form (`gbif` → GBIF, `scanbugs` → SCAN, `ecdysis` → Ecdysis); a record
carried by several aggregators keeps its combined key (`gbif/scanbugs` → “GBIF / SCAN”)
instead of counting once under each, so the panel stays one share of one whole. A blank key
is “Unknown.” No aggregator is inferred from institution, license, or URL.

**Institutions.** Recorded GBIF `institutionID` takes precedence over `institutionCode`;
codes label institutions. A code-only record joins an ID only when that code maps to a
single ID. Otherwise code-only ambiguity and conflicting occurrence assignments count
as “Conflicting attribution.” Repeated identical GBIF rows do not multiply image counts.
Distinct IDs sharing a code stay separate, with IDs added to their labels. Codes lacking
IDs remain code-based groups; their global uniqueness cannot be established from these
data. No URL-based inference or institution-name expansion occurs. Unattributed/conflicting
images are excluded from the ranking but retained in denominators and supporting tables.

**Geography.** Coordinate availability requires both values to parse as finite numbers.
An out-of-range pair or `(0, 0)` is still recorded; validation is shown separately.
Detailed locality requires nonblank `locality` or `verbatim_locality`; country/state alone
does not qualify. Validation categories come directly from the prepared coordinate table,
with missing joined results labeled “Not evaluated.” They are not recomputed here.

**Taxonomy matching.** Status and method each use all images or all distinct referenced
input-taxon keys, including unresolved outcomes. Unreferenced matching rows are excluded.
Input taxa are not accepted species. Images lacking an input-taxon key appear as
unclassified in image panels but cannot be counted as distinct input taxa.

**Benchmark.** Use the existing CSV; exclude `Flat (brute-force)` as in the original
notebook, while retaining `No Index (baseline)`. No performance measurements are rerun.

## Exports and validation

Each figure exports PDF, SVG (editable text), and 300-dpi PNG plus its underlying summary
CSV files into `analyses/results/`. Counts, unrounded percentages, denominator, and
population are included in composition CSVs. Display percentages round to one decimal.
Repeated runs replace outputs of the same name. `BIOCOSMOS_ANALYSES_OUTPUT` can select
another directory strictly within `analyses/`. Generated results and environments are ignored.

```bash
uv run --project analyses pytest analyses/tests -q
uv run --project analyses ruff check analyses
uv run --project analyses ruff format --check analyses
```

Tests use a small synthetic DuckDB containing duplicate GBIF records, conflicting
institution attribution, subspecies/genus matches, unknowns, and invalid coordinates.
They check denominators, join cardinality, read-only behavior, and execute all three
notebooks in real Jupyter kernels. Executed test notebooks and figures go to
`analyses/results/fixture-validation/`; these are **synthetic checks, not publication data**.
Source notebooks remain unexecuted with no stale outputs. Inspect actual-data exports
before publication, especially institution labels and any large unresolved categories.

**Validated-coordinate grid (panel F).** The data summary exports the grid it draws as
`dataset_overview_cells.csv`. Only prepared `VALID` coordinates enter a fixed EPSG:8857
equal-area grid, positioned by the parsed `latitude`/`longitude` stored in the validation
table (not a re-parse of the raw image fields):
100 × 100 km (10,000 km²), anchored at projected (0, 0), with lower-inclusive,
upper-exclusive boundaries. Cells are not clipped to land. The panel counts images,
including unresolved identifications; the exported table also carries distinct MATCHED
accepted species per cell, using the same subspecies and species-rank fallback rules as
composition. Gray land indicates no validated images. Counts are strongly right-skewed,
so the color scale is logarithmic, without correction for sampling effort. A cell whose
plotted column is zero is highlighted outside the scale rather than colored as its lowest
value. The cell export includes projected lower-left
bounds, CRS, area, and identified-image counts.

Coordinates marked VALID but unusable raise an error rather than silently changing the
population.
