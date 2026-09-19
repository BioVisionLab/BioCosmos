# colharmonize

Matches occurrence species names against a Catalogue of Life release. Reads the
occurrence DuckDB table read-only; the only write into it is the opt-in
`--write-back-table`.

```bash
uv run colharmonize init
uv run colharmonize inspect --db occurrences.duckdb --list-tables
uv run colharmonize inspect --db occurrences.duckdb --table main.occurrence \
  --map scientific_name=species
uv run colharmonize run --db occurrences.duckdb --table main.occurrence \
  --map scientific_name=species --col NameUsage.tsv --reports-dir reports \
  --csv --plot
```

Writes `taxonomy_update.duckdb` and `run.json`, plus `taxonomy_summary.csv`
with `--csv` and `taxonomy_match_summary.png` with `--plot`. With
`--reports-dir` they land in `<reports-dir>/taxonomy/<run_id>/` and
`latest.json` is updated to point at the run; `--output` writes to an explicit
directory instead. See [`reports/`](../../reports) for the artifact contract.

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

`--write-back-table main.taxonomy_lookup` instead copies a compact lookup into
the source database; it creates a new table and fails if that table exists.

`--config harmonize.toml` supplies the same settings; CLI values win. The file
may also hold `geoharmonize`'s tables, which are ignored here. Run
`colharmonize init --output -` to print the template.

The matching algorithm — normalization, candidate methods, scoring, the
species → subspecies → genus rank cascade, and the ambiguity rules — is
specified in the upstream project, <https://github.com/hhandika/col-taxonomy>.
