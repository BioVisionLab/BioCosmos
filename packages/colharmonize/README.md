# colharmonize

Match occurrence scientific names against a Catalogue of Life (ColDP) release. The source DuckDB database is opened read-only unless `--write-back-table` is passed.

The BioCosmos backend runs the same matcher automatically at startup, so running the CLI is not required to start the site. Use the CLI to inspect source tables, tune matching thresholds, or export standalone CSV summaries and plots.

## Usage

Run from the repository root with the backend stopped:

```bash
# Write a starter harmonize.toml configuration file (use "-o -" to print to stdout)
uv run colharmonize init

# Inspect tables and detected taxonomic columns
uv run colharmonize inspect --db occurrences.duckdb --list-tables
uv run colharmonize inspect --db occurrences.duckdb --table main.image_meta \
  --map scientific_name=species --map family=family --map order=order

# Build or rebuild the cached Catalogue of Life reference index
uv run colharmonize index --col "$COL_DIR/NameUsage.tsv"

# Run taxonomic matching and export CSV and plot summaries
uv run colharmonize run --db "$DUCK_DIR/biocosmos.duckdb" \
  --table main.image_meta --map scientific_name=species \
  --map family=family --map order=order --map class=class --map kingdom=kingdom \
  --col "$COL_DIR/NameUsage.tsv" --reports-dir reports --csv --plot

# Regenerate CSV or plot summaries from an existing taxonomy_update.duckdb
uv run colharmonize summarize --input reports/taxonomy/<run_id>/taxonomy_update.duckdb --csv --plot
```

## Outputs

Each `run` produces `taxonomy_update.duckdb` and `run.json` (plus `taxonomy_summary.csv` with `--csv` and `taxonomy_match_summary.png` with `--plot`). When `--reports-dir` is used, artifacts are written to `<reports-dir>/taxonomy/<run_id>/` and `<reports-dir>/latest.json` is updated (see [`reports/README.md`](../../reports/README.md)).

`taxonomy_update.duckdb` contains:

- `input_taxa` and `input_taxon_variants`: deduplicated input names and their original column values
- `taxonomy_matches`: one row per `input_taxon_key` with `update_status` (`MATCHED`, `AMBIGUOUS`, `UNMATCHED`), `match_method` (`EXACT_ACCEPTED`, `EXACT_SYNONYM`, `EXACT_CANONICAL`, `UNIQUE_FAMILY_EPITHET`, `SPELLING_GENUS`, `SPELLING_EPITHET`, `FUZZY_TYPO`, `AMBIGUOUS`, `UNMATCHED`), and the accepted Catalogue of Life classification
- `taxonomy_candidates`: ranked candidate matches considered during scoring
- `summary_metrics` and `run_metadata`

To join results back to the source table in SQL:

```sql
ATTACH 'reports/taxonomy/<run_id>/taxonomy_update.duckdb' AS harmonized;

SELECT src.*, m.accepted_name, m.update_status, m.match_method
FROM main.image_meta src
LEFT JOIN harmonized.input_taxon_variants v
  ON src.species = v.original_scientific_name
 AND src.family IS NOT DISTINCT FROM v.original_family
LEFT JOIN harmonized.taxonomy_matches m USING (input_taxon_key);
```

Pass `--write-back-table main.taxonomy_lookup` to copy a compact lookup table directly into the source DuckDB database (fails if the destination table already exists).

## Configuration

Pass `--config harmonize.toml` to load `[run]`, `[columns]`, and `[matching]` settings from a TOML file (CLI flags override file values). In `[matching]`, `default_order` can be set when all records belong to a single order so records with a blank `order` column are still protected against cross-order homonyms.

## Development

```bash
uv run --package colharmonize pytest packages/colharmonize/tests -q
uv run ruff check packages/colharmonize && uv run ruff format --check packages/colharmonize
```
