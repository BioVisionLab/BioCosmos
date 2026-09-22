# Temporal Analysis Plan & Context

Handoff notes for continuing `temporal_analysis.ipynb` — how does mean cosine
distance in a species' embeddings change over time, per wing side (dorsal /
ventral)? This file captures what's been decided and built so far, and what's
left before this becomes a "cosine distance over time" chart on species
detail pages.

## Data model findings (important — not obvious from the schema)

- `image_meta` (in the DuckDB file at `DUCK_DIR/biocosmos.duckdb`) has **no
  date column of its own**.
- Per-image observation dates come from GBIF: **`image_meta.uuid` joins to
  `gbif_meta.occurrenceID`**, which carries a Darwin Core `eventDate` string.
  This is the only way to get an image-level date.
- Only `gbif`-sourced images are joinable this way — `ecdysis` and
  `scanbugs`-sourced images (`image_meta.source_db`) have no date path at all
  and are permanently excluded from temporal analysis.
- Even among gbif-sourced images, `eventDate` coverage is partial. For
  `clossiana_polaris`: 231/257 images dated (89.9%). For `kallima_sylvia`:
  219/425 dated (51.5%). Expect this to vary a lot by species.
- `eventDate` values come in multiple formats: `YYYY-MM-DD`, `YYYY-MM`, and
  ranges like `YYYY-MM-DD/YYYY-MM-DD`. We currently just take the first 4
  characters of the range start as the `year` and ignore finer (month/day)
  precision.

## Decisions made so far

- **Time buckets**: `BUCKET_YEARS` (default 10, i.e. decades) — a notebook
  parameter, not hardcoded. Buckets are labeled by their start year (e.g.
  bucket 1930 covers 1930–1939).
- **Minimum images per bucket**: `MIN_BUCKET_IMAGES` (default 5). A
  `(side, bucket)` group below this is dropped entirely rather than merged
  into a neighboring bucket or combined across sides.
- **Dorsal and ventral are never combined.** They represent different data.
  If one side doesn't have enough images in a given bucket, that side is
  simply absent from that bucket — the other side is unaffected. This means
  a species can end up with only one side represented at all (see
  `clossiana_polaris` below).
- **Distance metric — two are computed, `baseline` is the preferred
  default for visualization** (the user's explicit preference, expressed
  after initially defaulting to `overall`):
  - `baseline` (**default**): distance from each bucket's centroid to that
    side's *earliest* bucket centroid. Shows cumulative drift from the
    earliest dated period.
  - `overall` (kept as an alternate option via the `DISTANCE_METRIC`
    parameter): distance from each bucket's centroid to that side's
    whole-species centroid (computed over all available images for that
    side, dated or not). Sensitive to whichever decade happens to have the
    most images, since the whole-species centroid is an unweighted average.

## What's implemented in the notebook right now

In order, the notebook now:
1. Connects to DuckDB (`image_meta`, `gbif_meta` tables) and LanceDB
   (`unicom_embeddings`).
2. `load_metadata()` — existing function, loads `img_id`/`species`/`side`
   for one species (or all species ≥ `MIN_SPECIES_IMAGES`).
3. `load_dates()` + `parse_event_year()` — new. Joins in `eventDate` via
   `image_meta.uuid = gbif_meta.occurrenceID`, parses to a `year` column,
   merges into `meta` (images with no resolvable date get `year = null` and
   are excluded downstream, but still usable elsewhere).
4. A histogram cell showing images-per-year per side, used to sanity-check
   bucket sizing before trusting any distance numbers.
5. `compute_centroids()` — existing function, whole-species centroid per
   `(species, side)`.
6. `compute_temporal_centroids()` — new. Buckets dated images by
   `(side, bucket)`, drops groups below `MIN_BUCKET_IMAGES`, returns
   per-bucket centroids + image counts.
7. `compute_temporal_distances()` — new. Computes both `overall` and
   `baseline` distances for every retained bucket; returns a long-format
   polars DataFrame (`side`, `bucket`, `n`, `metric`, `distance`).
8. A line chart: x = bucket start year, y = distance, one line per side
   (colored via `SIDE_COLORS`), points annotated with `n` images, filtered
   to `DISTANCE_METRIC`.

All of this has been executed end-to-end against the real local database (no
lingering errors) and tested on two species:
- `clossiana_polaris`: only `dorsal` ever meets `MIN_BUCKET_IMAGES` — ventral
  images are too sparse per decade (max ~2/year) to produce any ventral
  buckets. 10 dorsal buckets, spanning 1890–1999.
- `kallima_sylvia`: both sides produce buckets (7 dorsal, 6 ventral).

Species list for quick testing (set via `SPECIES_FILTER`):
`clossiana_polaris`, `kallima_sylvia`, `papilio_sataspes` (untested yet).

## Known caveats to keep in mind

- The `overall` metric can be dominated by whichever bucket has the most
  images (unweighted centroid) — e.g. for `clossiana_polaris`, a single
  1930s bucket has 99 of ~230 dated images. This is part of why `baseline`
  is now preferred.
- Species/sides with sparse or one-sided date coverage will produce partial
  or single-side charts — this is expected behavior, not a bug, per the "no
  combining sides" decision above.
- No per-image capture date exists outside the GBIF join — if finer-grained
  or more complete dates are ever needed, that requires changes to the
  upstream `image_meta` ingestion pipeline (outside this repo), not just
  this notebook.

## Next step: generalize to all species (not yet started)

This was explicitly deferred until the single-species prototype was
validated. When picking this up:

1. Port `load_dates()`, `compute_temporal_centroids()`, and
   `compute_temporal_distances()` into a standalone script, mirroring the
   structure of `backend/scripts/precompute_similarity.py` (CLI args via
   `argparse`, batch-friendly numpy/polars operations, a `--species` flag
   for single-species runs during testing, a `--force` flag to rebuild).
2. Run it across all species with ≥ `MIN_SPECIES_IMAGES` images (reuse the
   existing threshold), computing both distance metrics per
   `(species, side, bucket)`.
3. Store results in a new DuckDB table, e.g.
   `species_temporal_drift(species, side, bucket, distance_overall,
   distance_baseline, n_images)`, created/populated the same way
   `precompute_similarity.py` builds `species_similarity` (`CREATE TABLE IF
   NOT EXISTS`, `DELETE ... WHERE species = ?` + insert for per-species
   runs, full drop+recreate for `--force`).
4. Add a new backend query class mirroring
   `backend/app/query/precomputed_similarity.py`
   (`PrecomputedSpeciesSimilarity`) to read from this table.
5. Add a new router endpoint, e.g.
   `GET /species/{scientific_name}/temporal-drift`, in
   `backend/app/routers/species_data.py`, alongside the existing
   `/biology`, `/similar`, `/specimens` endpoints. Response shape: a list of
   `{bucket, distanceBaseline, distanceOverall, imageCount, side}` objects
   (camelCase via `alias_generator=to_camel`, matching existing payload
   models like `VisuallySimilarSpeciesPayload`).
6. Frontend: add a chart to the species detail page consuming this
   endpoint, defaulting to the `baseline` metric per the plotting default
   established here.
7. Decide how to handle species/sides with too few dated buckets to show a
   meaningful trend (e.g. require ≥ 2 retained buckets per side to include
   that side in the response at all).
