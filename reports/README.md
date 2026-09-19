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

## Planned backend consumption (not yet implemented)

The backend does not read this directory yet. The intended design, for the
follow-up task:

1. Add a `ColConfig` to `backend/app/configs/config.py` following the existing
   `GbifConfig` / `LepTraitConfig` template (`path` from the `COL_DIR`
   environment variable plus the YAML `file`, plus `table` and `skip`).
   `COL_DIR` already exists in `backend/.env`, but must be declared on
   `AppSettings` in `backend/app/main.py` and set in `docker-compose.yml`.
2. Extend the `col:` stanza in `backend/app/configs/config.yaml` with `table:`
   and `reports_dir:`.
3. When `skip` is false, read `latest.json`, then the manifest it names, then
   the `database` artifact's `sha256`. Compare it against the value recorded in
   an `ingestion_state` table in the backend DuckDB, and skip the load when
   they match.

Step 3 is the freshness check current ingestion lacks: `gbif_meta` and
`lep_traits_consensus` are created with `CREATE TABLE IF NOT EXISTS`, so a
changed source file with an unchanged name is silently ignored today.
