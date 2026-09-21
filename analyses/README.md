# Publication analyses and backend benchmarks

Notebooks in `notebooks/` only load figure-ready summaries, draw figures, and export them.
`publication.py` holds configuration, read-only queries, aggregation, and reusable plotting.
The separate `benchmarks/` workflow tests backend vector-index performance on an isolated copy.
Neither workflow changes a backend source database.

## Indexing and backend performance

`benchmarks/image_indexing.ipynb` is independent of publication plotting and DuckDB.
Its implementation lives in `benchmarks/lance_indexing.py`, with no publication imports.

```bash
uv sync --project analyses --extra indexing --locked
uv run --project analyses --extra indexing jupyter lab analyses/benchmarks/image_indexing.ipynb
```

The optional indexing dependencies pin LanceDB to `0.39.0`, matching the backend's
current root lockfile. Keep this pin aligned when upgrading the backend. `LANCE_DIR`
comes from `backend/.env` (existing environment variables override it); the database
filename and image table name come from backend YAML. Relative paths resolve from
`backend/`. No backend startup code, embedding models, or external `pyMimicry` client
are imported.

Run setup/configuration cells first to inspect the source and select sample size,
repetitions, warmup, partitions, PQ subvectors, and optional query controls. Defaults
test UNICOM and CLIP against exact search, IVF-PQ, IVF-HNSW-SQ, and IVF-HNSW-PQ.
The same seeded sample across the full table is used for each candidate. Both the
exact reference and ANN searches explicitly use the backend's cosine metric.
Subvector counts must divide embedding dimensions; ANN training requires at least
256 rows and at least as many rows as partitions. Missing/invalid vectors and duplicate
image IDs are errors, rather than silently changing the benchmark population.

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

Indexing tests are optional with the dependency extra:

```bash
uv run --project analyses --extra indexing pytest analyses/tests -q
```

## Run with uv

This directory is a standalone uv project so its dependencies, lockfile, and environment
do not change the backend or root workspace. From the repository root:

```bash
uv sync --project analyses --locked
uv run --project analyses jupyter lab analyses/notebooks
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

| Notebook | Outputs |
| --- | --- |
| `data_summary.ipynb` | Family and dorso-ventral proportions; top ten institutions and species |
| `georeference.ipynb` | Coordinate/locality availability pies; coordinate-validation category bars |
| `taxonomy_harmonization.ipynb` | Match-status pies and match-method bars for images and unique input taxa |
| `index_perf.ipynb` | Recorded index latency versus recall@10 |

**Figure style.** Colours come from seaborn, defaulting to the ColorBrewer `Dark2`
qualitative palette set by `publication_style()`. Bars are one colour: each bar is a labelled
category, so per-bar colour would imply a grouping that is not there. Every pie uses the same
palette in the same order, largest share first, so the figures read as one set; a category's
colour therefore follows its rank within its own panel, not a fixed meaning. `category_plot()`
draws a pie when a summary compares exactly two classes of a complete population and bars
otherwise; pass `kind="pie"` for a whole-population panel worth reading as shares even with more
than two classes (match status does this), `kind="bar"` to force bars, and `palette=` for another
seaborn palette. Pies never take `top`/`exclude`, because a ranked subset is not a whole.

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
They check denominators, join cardinality, read-only behavior, and execute all four
notebooks in real Jupyter kernels. Executed test notebooks and figures go to
`analyses/results/fixture-validation/`; these are **synthetic checks, not publication data**.
Source notebooks remain unexecuted with no stale outputs. Inspect actual-data exports
before publication, especially institution labels and any large unresolved categories.
