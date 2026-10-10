# colharmonize

Match occurrence species names against a Catalogue of Life release. The CLI
reads the source DuckDB table read-only unless you pass `--write-back-table`.

The BioCosmos backend runs the same matcher at startup. Use the CLI to inspect
inputs, tune matching, or export summaries.

## Usage

Run from the repository root. Stop the backend before accessing its live DuckDB
file.

```bash
uv run colharmonize init
uv run colharmonize inspect --db occurrences.duckdb --list-tables
uv run colharmonize inspect --db occurrences.duckdb --table main.occurrence \
  --map scientific_name=species
uv run colharmonize run --db occurrences.duckdb --table main.occurrence \
  --map scientific_name=species --col NameUsage.tsv --reports-dir reports \
  --csv --plot
```

## Output

Each run writes `taxonomy_update.duckdb` and `run.json`. Add `--csv` for
`taxonomy_summary.csv` and `--plot` for `taxonomy_match_summary.png`.

With `--reports-dir`, outputs go to `<reports-dir>/taxonomy/<run_id>/` and
`latest.json` points to the run. Use `--output` to choose an explicit directory.
See the [report format](../../reports/README.md).

The output database contains `input_taxa`, `input_taxon_variants`,
`taxonomy_matches`, `taxonomy_candidates`, `summary_metrics`, and
`run_metadata`. Join a run back to the source by the original fields:

```sql
ATTACH 'reports/taxonomy/<run_id>/taxonomy_update.duckdb' AS harmonized;
SELECT occurrence.*, matches.accepted_name, matches.update_status
FROM occurrence
LEFT JOIN harmonized.input_taxon_variants variants
  ON occurrence.species = variants.original_scientific_name
 AND occurrence.family IS NOT DISTINCT FROM variants.original_family
LEFT JOIN harmonized.taxonomy_matches matches USING (input_taxon_key);
```

`--write-back-table main.taxonomy_lookup` also copies a compact lookup into the
source database. It creates a new table and fails if the destination exists.

## Configuration

Use `--config harmonize.toml` to read settings from a file. CLI values take
precedence. The file may also contain `geoharmonize` sections; this tool ignores
them. Run `colharmonize init --output -` to print the template.

The [upstream project](https://github.com/hhandika/col-taxonomy) documents
normalization, candidate methods, scoring, the species → subspecies → genus rank
cascade, and ambiguity rules.

## Development

```bash
uv run --package colharmonize pytest packages/colharmonize/tests -q
```
