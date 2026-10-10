# similarity

Precompute the visually similar species shown on species pages. Results go into
the backend's `species_similarity` table, read by
`backend/app/query/precomputed_similarity.py`.

## How similarity is computed

For each species and side (dorsal or ventral), the tool computes a centroid from
L2-normalized UNICOM embeddings and compares it with every image by cosine
distance, using a batched matrix multiplication. It takes the nearest `--top-k`
images, keeps the nearest image of each other species, and saves the first
`--limit` species with their ranks and distances.

Species and side labels come from `image_meta` (`species`, `class_dv`), the
backend's filtered view. Families in `image_metadata.exclude_families`
(currently Castniidae) are excluded from queries and matches even though their
embeddings remain in LanceDB. The computation holds all embeddings in memory:
about 600,000 × 768 float32 values, or roughly 2 GB.

## Usage

Run from the repository root with `$DUCK_DIR` and `$LANCE_DIR` exported in your
shell. Stop the backend first: the command writes into its DuckDB file, and
DuckDB allows a single writer.

```bash
uv run similarity run --db "$DUCK_DIR/biocosmos.duckdb" --lance-dir "$LANCE_DIR/biocosmos.lance"
```

A full run replaces all rows in one transaction. Use
`--species "vanessa cardui"` to recompute only that species, or `--force` to
drop and recreate the table first.

Rerun after changing the embeddings, image metadata, or excluded families. After
changing `image_metadata.exclude_families`, restart the backend to refresh
`image_meta`, then stop it before running similarity.

## Options

| Option               | Default              | Meaning                                                  |
| -------------------- | -------------------- | -------------------------------------------------------- |
| `--lance-table`      | `nymphalidae`        | LanceDB embedding table                                  |
| `--meta-table`       | `image_meta`         | Filtered metadata view supplying image labels            |
| `--similarity-table` | `species_similarity` | Output table                                             |
| `--top-k`            | 800                  | Nearest images fetched per centroid before deduplication |
| `--limit`            | 10                   | Similar species kept per species × side                  |

## Development

```bash
uv run --package similarity pytest packages/similarity/tests -q
uv run ruff check packages/similarity && uv run ruff format --check packages/similarity
```
