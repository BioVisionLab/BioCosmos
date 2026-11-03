# similarity

Precompute the visually similar species displayed on BioCosmos species pages. Results are written to the `species_similarity` table in `biocosmos.duckdb` and read by `backend/app/query/precomputed_similarity.py`.

## How Similarity Is Computed

For every species and wing side (`dorsal` or `ventral`):

1. Computes the L2-normalized mean (centroid) of that species' UNICOM embeddings for that side.
2. Compares each centroid against all images in LanceDB by cosine distance using batched matrix multiplication.
3. Fetches the nearest `--top-k` images (default `800`), keeps the closest image of each distinct other species, and stores the top `--limit` species (default `10`) along with their rank and cosine distance.

Species and wing-side labels are read from the backend's filtered `image_meta` view (`species`, `class_dv`). Families listed in `image_metadata.exclude_families` (such as Castniidae) are automatically excluded from both queries and candidate matches. All embeddings (~600,000 × 768 `float32` values, ~2 GB) are held in memory during the batch computation.

## Usage

Run from the repository root with `$DUCK_DIR` and `$LANCE_DIR` exported in your shell. **Stop the backend first** so `similarity` can open `biocosmos.duckdb` for writing:

```bash
uv run similarity run --db "$DUCK_DIR/biocosmos.duckdb" --lance-dir "$LANCE_DIR/biocosmos.lance"
```

- A full run replaces all rows in a single transaction.
- Pass `--species "vanessa cardui"` to recompute a single species.
- Pass `--force` to drop and recreate `species_similarity` before inserting.

Re-run `similarity run` whenever embeddings, image metadata, taxonomy overrides, or `image_metadata.exclude_families` change (restart the backend first if `exclude_families` changed so the `image_meta` view is updated, then stop it).

## CLI Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `--db` | required | Path to the backend DuckDB database (`biocosmos.duckdb`) |
| `--lance-dir` | required | Path to the LanceDB directory (`biocosmos.lance`) |
| `--lance-table` | `nymphalidae` | LanceDB table containing image embeddings |
| `--meta-table` | `image_meta` | DuckDB view/table supplying species and `class_dv` labels |
| `--similarity-table` | `species_similarity` | Destination DuckDB table |
| `--top-k` | `800` | Nearest images fetched per centroid before species deduplication |
| `--limit` | `10` | Visually similar species retained per species and wing side |
| `--species` | all | Recompute only the specified species |
| `--force` | `False` | Drop and recreate `--similarity-table` |

## Development

```bash
uv run --package similarity pytest packages/similarity/tests -q
uv run ruff check packages/similarity && uv run ruff format --check packages/similarity
```
