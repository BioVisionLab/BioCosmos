# morphospace

Precompute dorso-ventral PCA morphospaces, morphological disparity, and dorsal–ventral Mantel correlations from 768-D UNICOM image embeddings. The resulting DuckDB tables power the morphospace views on species, genus, and family pages as well as the publication figures in [`analyses/`](../../analyses/README.md).

## Computed Quantities

| Quantity | Definition |
| :--- | :--- |
| **Centroid** | Mean of a species' L2-normalized UNICOM vectors for one wing side (`dorsal` or `ventral`), re-normalized to unit length. Computed when that side has at least `--min-images` images (default `3`). |
| **Dispersion** | Mean cosine distance from a species' images to its side centroid (intraspecific variation). |
| **Representative image** | The medoid specimen image (the image closest to the species' side centroid). |
| **Scope** | `all` (the entire butterfly collection), each family, and each genus with at least `--min-scope-species` species (default `3`). |
| **Shared PCA** | One PCA per scope fitted on stacked dorsal and ventral species centroids so both wing sides share the same PC1–PC3 axes. Signs are stabilized by setting each component's largest loading positive. |
| **Species ellipse** | Mean, standard deviations, and PC1 × PC2 correlation of a species' individual images projected onto the scope's PCA axes. |
| **Axis extremes** | The species at the minimum and maximum ends of each PCA axis, alongside their medoid images. |
| **Disparity** | Sum of variances of species centroids across all 768 embedding dimensions per scope and side (equal to half the mean squared Euclidean distance, or mean pairwise cosine distance for unit vectors). Also rarefied to `--rarefy-k` species (`5` by default) over `--bootstrap` resamples (`200` by default, reporting mean and 95% interval). |
| **Dorso-ventral divergence** | Cosine distance between a species' dorsal and ventral centroids. |
| **Dorso-ventral correlation** | Mantel correlation (`r`) between dorsal and ventral pairwise species distance matrices for scopes with at least 5 species represented on both sides (with a permutation p-value up to `--permutation-max-species`). |

Embeddings are streamed from LanceDB in two passes so the full ~600,000 × 768 collection fits comfortably in memory.

## Usage

Run from the repository root with `$DUCK_DIR` and `$LANCE_DIR` exported in your shell. **Stop the backend first** (`inspect` and `run` open the databases read-only, and `integrate` writes to `biocosmos.duckdb`, which cannot be attached while FastAPI holds it open):

```bash
# Check eligible scopes and species counts
uv run morphospace inspect --db "$DUCK_DIR/biocosmos.duckdb"

# Compute morphospaces and save artifacts under reports/morphospace/<run_id>/
uv run morphospace run --db "$DUCK_DIR/biocosmos.duckdb" --lance-dir "$LANCE_DIR/biocosmos.lance"

# Copy the latest run's tables into biocosmos.duckdb
uv run morphospace integrate --db "$DUCK_DIR/biocosmos.duckdb" --replace
```

## Output and Database Tables

`morphospace run` writes `morphospace.duckdb` and `morphospace_run.json` under `reports/morphospace/<run_id>/` and updates `reports/latest.json` (see [`reports/README.md`](../../reports/README.md)).

`morphospace integrate` copies the run into five tables in `biocosmos.duckdb` inside a single transaction (configured under `morphospace:` in `backend/app/configs/config.yaml`):

| Table | Contents (one row per ...) |
| :--- | :--- |
| `morphospace_scope` | Scope (`all`, family, or genus): species counts, explained variance, Mantel correlation, and `run_id` |
| `morphospace_points` | Scope × species × wing side: PC1–PC3 coordinates, image ellipse parameters, and medoid `img_id` |
| `morphospace_species` | Species: per-side image counts, dispersion, medoid `img_id`, and dorso-ventral divergence |
| `morphospace_disparity` | Scope × wing side: full `sum_var` and rarefied disparity (`rarefied_mean`, 95% CI) |
| `morphospace_extremes` | Scope × PC axis × end (`low` / `high`): extreme species and medoid `img_id` |

Re-run `morphospace run` and `morphospace integrate --replace` whenever embeddings, taxonomy, or `image_metadata.exclude_families` change.

## Development

```bash
uv run --package morphospace pytest packages/morphospace/tests -q
uv run ruff check packages/morphospace && uv run ruff format --check packages/morphospace
```
