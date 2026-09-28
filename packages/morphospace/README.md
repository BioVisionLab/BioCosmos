# morphospace

Dorso-ventral morphospaces, disparity and integration from the UNICOM image
embeddings.

## What it computes

Each image is labelled with its side (`image_meta.class_dv`: dorsal or ventral)
and its harmonized accepted species, genus and family (`image_meta_taxonomy`,
`MATCHED` only). These are the same groupings the backend's species, genus and
family pages use. Records resolved only to genus rank are left out, and so
are the families in `MorphospaceParameters.exclude_families` (Castniidae, moths
imaged with the butterflies), which the run manifest records. `image_meta` is
itself a view that drops the families in the backend's
`image_metadata.exclude_families`, so both filters agree.

| Quantity | Definition |
| --- | --- |
| Centroid | Mean of a species' L2-normalized UNICOM vectors for one side, re-normalized. Kept when the species has at least `--min-images` photographs of that side. |
| Dispersion | Mean cosine distance of a species' photographs to that centroid (intraspecific variation). |
| Representative image | The medoid: the photograph closest to the centroid. |
| Scope | `all`; every family; every genus with at least `--min-scope-species` species. |
| Shared PCA | One PCA per scope, fitted on the dorsal and ventral centroids stacked, so both sides share axes. Fitted on species seen from both sides when there are at least 3 of them. PC signs are pinned (largest loading positive) so reruns are stable. |
| Ellipse | Mean, SDs and correlation of a species' photographs projected on PC1 × PC2. |
| Axis extremes | The species at each end of each axis, which show what the axis captures. |
| Disparity | Sum of variances of the species centroids in the full 768-d embedding, per scope and side. It is also rarefied to `--rarefy-k` species (`--bootstrap` resamples, 95% interval). For unit vectors, it equals the mean pairwise cosine distance. |
| Dorso-ventral divergence | Cosine distance between a species' dorsal and ventral centroids. |
| Dorso-ventral integration | Mantel r between the dorsal and ventral species distance matrices, for scopes with at least 5 species seen from both sides. There is a permutation p-value up to `--permutation-max-species`. |

The embeddings (about 600k × 768) are streamed from LanceDB twice and are never
held in memory at once. A full run over the collection takes under a minute.

## Usage

Run these from the repository root. Both stores are opened read-only by `inspect`
and `run`. **Stop the backend before `integrate`:** DuckDB allows a single
writer.

```bash
uv run morphospace inspect --db "$DUCK_DIR/biocosmos.duckdb"
uv run morphospace run --db "$DUCK_DIR/biocosmos.duckdb" --lance-dir "$LANCE_DIR/biocosmos.lance"
uv run morphospace integrate --db "$DUCK_DIR/biocosmos.duckdb" --replace
```

`run` writes `reports/morphospace/<run_id>/morphospace.duckdb` and
`morphospace_run.json`, then points `reports/latest.json` at the run.
`integrate` copies the latest run, or `--run <dir>`, into five tables in one
transaction:

| Table | One row per |
| --- | --- |
| `morphospace_scope` | scope: explained variance, integration, run id |
| `morphospace_points` | scope × species × side: PC1–PC3, ellipse, medoid |
| `morphospace_species` | species: per-side count, dispersion, medoid; divergence |
| `morphospace_disparity` | scope × side |
| `morphospace_extremes` | scope × axis × end |

The names are listed under `morphospace:` in `backend/app/configs/config.yaml`,
which the backend and `analyses/` both read. Until the tables are integrated,
the `/morphospace` endpoints answer 404 and the pages leave the section out.

The publication figure is `analyses/notebooks/morphospace.ipynb`.

## Development

```bash
uv run --package morphospace pytest packages/morphospace/tests -q
uv run ruff check packages/morphospace && uv run ruff format --check packages/morphospace
```
