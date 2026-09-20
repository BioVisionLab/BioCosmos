# reports/

Generated run artifacts from the harmonization tools in
[`packages/`](../packages). Everything here except this file and `.gitkeep` is
gitignored: the outputs are large, binary, and reproducible from their inputs.

```
reports/
  latest.json                     pointer to the newest run of each kind
  taxonomy/<run_id>/              written by `colharmonize run`
    run.json
    taxonomy_update.duckdb
    taxonomy_summary.csv          with --csv
    taxonomy_match_summary.png    with --plot
  geography/<run_id>/             written by `geoharmonize validate-coordinates`
    coordinate_run.json
    coordinate_validation.duckdb
```

Both tools write here when given `--reports-dir reports` (or `reports_dir` in
`harmonize.toml`), and default to it when a `reports/` directory exists. `run_id`
is a UUID4 generated per run, so runs never overwrite each other.

## Manifest contract

Each run writes a manifest — `run.json` or `coordinate_run.json` — as
deterministic JSON (`indent=2`, `sort_keys=True`) through a temporary file and
`os.replace`, so a reader never sees a partial file.

Fields relevant to a consumer:

| Field | Meaning |
| --- | --- |
| `schema_version` | Version of this contract. Currently `1`. |
| `run_id` | UUID4 of the run; also the directory name |
| `package_version` | Version of the tool that produced the run |
| `started_at`, `completed_at`, `runtime_seconds` | Timing, ISO-8601 UTC |
| `col_sha256` / `gadm_sha256` | SHA-256 of the **input** reference file |
| `detected_columns` | Logical field to source column mapping actually used |
| `outputs` | Role to absolute path, including `manifest` |
| `artifacts` | One entry per produced file: `role`, `path`, `bytes`, `sha256` |
| `counts` | Row counts by outcome |

`artifacts[].sha256` is taken **after** each file reaches its final path, so it
describes exactly what a consumer will read. The manifest does not contain its
own digest.

`latest.json` points at the newest run of each kind. Each tool rewrites only its
own key, so the two can run independently:

```json
{
  "schema_version": 1,
  "taxonomy":  {"run_id": "...", "completed_at": "...", "manifest": "taxonomy/<run_id>/run.json"},
  "geography": {"run_id": "...", "completed_at": "...", "manifest": "geography/<run_id>/coordinate_run.json"}
}
```

## Backend consumption

**The backend does not read this directory.** It harmonizes the occurrence
names itself, in-process, through the same `colharmonize` pipeline — see
`backend/app/services/taxonomy_update.py`. That happens at startup unless
`col.skip` is set, the same as every other source, and once the result is
current it costs nothing. Nothing here has to be run by hand for the site to
work.

What the service does, on each start:

1. Fingerprints the Catalogue of Life release and the distinct occurrence taxa.
   An unchanged fingerprint means there is nothing to do; a new image of a
   known species does not trigger a rematch.
2. Exports the taxonomy columns to a scratch database. DuckDB will not let a
   second handle open the file this process already holds, and the pipeline
   reads its input from a file, so the taxa travel rather than the connection.
3. Builds or reuses the CoL reference index. It is roughly 3.6 GB and takes
   about a minute, so it is cached — in `~/.cache/colharmonize` by default,
   shared with the CLI, or under `col.cache_dir` where `HOME` is not
   persistent.
4. Runs the matcher, then copies `taxonomy_matches`, `taxonomy_candidates` and
   `input_taxon_variants` into the application database and builds
   `image_meta_taxonomy` — one row per occurrence image.

`input_taxon_variants` is kept because the `original_*` columns on
`taxonomy_matches` are `min()` aggregates over a taxon's variants and so cannot
be joined back to individual occurrence rows.

Nothing in that sequence raises. A missing release, an unreadable one, or a
failed match leaves the API serving occurrence data without a taxonomic update,
and says so once at startup.

`taxon_rank` is deliberately not mapped. `image_meta` labels 163,895
occurrences `subspecies` while carrying a two-word binomial, plus 259 spelled
`subspec`; mapping the rank makes the matcher reject those as invalid
trinomials and 26% of the collection comes back `UNMATCHED`. Letting its own
species → subspecies → genus cascade decide instead:

| Mapping | Input taxa | Matched | Ambiguous | Unmatched |
| --- | --- | --- | --- | --- |
| with `taxon_rank=tax_rank` | 11,252 | 8,871 | 105 | 2,276 |
| without | 9,346 | 9,233 | 108 | **5** |

### The CLI

`colharmonize run` remains useful for work the backend does not do: tuning the
matching thresholds, and exporting `taxonomy_summary.csv` and
`taxonomy_match_summary.png` for inspection. Its artifacts land here.

```bash
uv run colharmonize run --db "$DUCK_DIR/biocosmos.duckdb" --table main.image_meta \
  --map scientific_name=species --map family=family --map order=order \
  --map class=class --map kingdom=kingdom \
  --col "$COL_DIR/NameUsage.tsv" --reports-dir reports --csv --plot
```

**Stop the backend first.** DuckDB allows a single writer: the API holds
`biocosmos.duckdb` open read-write, and `colharmonize` cannot attach to it —
even read-only — while that process is alive. This is why the backend runs the
pipeline in-process rather than shelling out to the CLI.
