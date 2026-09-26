# similarity

Precomputes the "visually similar species" the species pages show and writes
them into the backend's `species_similarity` table, which
`backend/app/query/precomputed_similarity.py` reads.

## What it computes

For each species × side (dorsal, ventral), the centroid of its L2-normalized
UNICOM embeddings is compared with every image by cosine distance (one batched
matrix multiply). The nearest `--top-k` images are then reduced to the nearest
image of each *other* species, and the first `--limit` of those are kept with
their rank and distance.

Labels come from `image_meta` (`species`, `class_dv`). That is the backend's
filtered view, so families in `image_metadata.exclude_families` (Castniidae)
are never a query species or a match, even though their embeddings are still in
LanceDB. All embeddings (about 600k × 768 float32, roughly 2 GB) are held in
memory.

## Usage

Run from the repository root. **Stop the backend first:** this writes into
the backend DuckDB, and DuckDB allows a single writer.

```bash
uv run similarity run --db "$DUCK_DIR/biocosmos.duckdb" --lance-dir "$LANCE_DIR/biocosmos.lance"
```

A full run replaces every row of the table in one transaction. `--species
"vanessa cardui"` recomputes one species and replaces only its rows. `--force`
drops and recreates the table first. Re-run after the embeddings, the image
metadata, or `exclude_families` change.

| Option | Default | Meaning |
| --- | --- | --- |
| `--lance-table` | `nymphalidae` | LanceDB embedding table |
| `--meta-table` | `image_meta` | Metadata view to label images with |
| `--similarity-table` | `species_similarity` | Output table |
| `--top-k` | 800 | Nearest images fetched per centroid before deduplication |
| `--limit` | 10 | Similar species kept per species × side |

## Development

```bash
uv run --package similarity pytest packages/similarity/tests -q
uv run ruff check packages/similarity && uv run ruff format --check packages/similarity
```
