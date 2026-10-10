# morphospace

Compute dorso-ventral morphospaces, disparity, and correlation from UNICOM image
embeddings. The resulting tables supply the species, genus, and family pages and
the publication notebooks.

## Computed quantities

| Quantity                  | Definition                                                                                                                                                                                                                                               |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Centroid                  | Mean of a species' L2-normalized UNICOM vectors for one side, normalized again. Retained when that side has at least `--min-images` images.                                                                                                              |
| Dispersion                | Mean cosine distance from a species' images to its centroid, measuring intraspecific variation.                                                                                                                                                          |
| Representative image      | The medoid: the image closest to the centroid.                                                                                                                                                                                                           |
| Scope                     | `all`; every family; every genus with at least `--min-scope-species` species.                                                                                                                                                                            |
| Shared PCA                | One PCA per scope, fitted on stacked dorsal and ventral centroids so both sides share axes. Uses species with both sides when at least three are available. The largest loading on each PC is set positive to keep axis directions stable across runs.   |
| Ellipse                   | Mean, standard deviations, and correlation of a species' images projected onto PC1 × PC2.                                                                                                                                                                |
| Axis extremes             | The species at each end of each axis, which show what the axis captures.                                                                                                                                                                                 |
| Disparity                 | Sum of variances of the species centroids in the full 768-dimensional embedding, per scope and side. It is also rarefied to `--rarefy-k` species (`--bootstrap` resamples, 95% interval). For unit vectors, it equals the mean pairwise cosine distance. |
| Dorso-ventral divergence  | Cosine distance between a species' dorsal and ventral centroids.                                                                                                                                                                                         |
| Dorso-ventral correlation | Mantel correlation (r) between the dorsal and ventral species distance matrices, for scopes with at least five species with both sides. There is a permutation p-value up to `--permutation-max-species`.                                                |

The computation streams the embeddings from LanceDB in two passes to limit
memory use. The collection has roughly 600,000 vectors of 768 dimensions.

## Usage

Run from the repository root with `$DUCK_DIR` and `$LANCE_DIR` exported in your
shell. Stop the backend before opening its live DuckDB file, including for
`inspect` and `run`: the API holds it open read-write. `inspect` and `run` open
the source stores read-only; `integrate` writes the results into DuckDB.

```bash
uv run morphospace inspect --db "$DUCK_DIR/biocosmos.duckdb"
uv run morphospace run --db "$DUCK_DIR/biocosmos.duckdb" --lance-dir "$LANCE_DIR/biocosmos.lance"
uv run morphospace integrate --db "$DUCK_DIR/biocosmos.duckdb" --replace
```

## Output and integration

`run` writes `reports/morphospace/<run_id>/morphospace.duckdb` and
`morphospace_run.json`, then points `reports/latest.json` at the run. Use
`integrate` to copy the latest run into five tables in one transaction, or pass
`--run <dir>` to select a run explicitly:

| Table                   | One row per                                             |
| ----------------------- | ------------------------------------------------------- |
| `morphospace_scope`     | scope: explained variance, correlation, run ID          |
| `morphospace_points`    | scope × species × side: PC1–PC3, ellipse, medoid        |
| `morphospace_species`   | species: per-side count, dispersion, medoid; divergence |
| `morphospace_disparity` | scope × side                                            |
| `morphospace_extremes`  | scope × axis × end                                      |

The names are listed under `morphospace:` in `backend/app/configs/config.yaml`,
which the backend and `analyses/` both read. Until the tables are integrated,
the `/morphospace` endpoints return 404 and the pages omit the morphospace
section.

Rebuild and integrate after changing the embeddings, taxonomy, or excluded
families. Restart the backend first when changing
`image_metadata.exclude_families` so the filtered metadata view is current. The
publication figure is generated by
[`morphospace.ipynb`](../../analyses/notebooks/morphospace.ipynb).

## Development

```bash
uv run --package morphospace pytest packages/morphospace/tests -q
uv run ruff check packages/morphospace && uv run ruff format --check packages/morphospace
```
