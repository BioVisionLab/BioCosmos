# geoharmonize

Validates occurrence coordinates against GADM administrative geography. Reads
the occurrence DuckDB table read-only and never modifies it.

```bash
uv run geoharmonize init
uv run geoharmonize inspect --db occurrences.duckdb --list-tables
uv run geoharmonize validate-coordinates --db occurrences.duckdb \
  --table main.occurrence --gadm gadm.gpkg --reports-dir reports
```

Writes `coordinate_validation.duckdb` and `coordinate_run.json`. With
`--reports-dir` they land in `<reports-dir>/geography/<run_id>/` and
`latest.json` is updated to point at the run; `--output` writes to an explicit
directory instead. See [`reports/`](../../reports) for the artifact contract.

Detects the Darwin Core fields `occurrenceID`, `decimalLatitude`,
`decimalLongitude`, `countryCode` or `country`, and `stateProvince`. Override
one with `--map FIELD=COLUMN`; the logical fields are `source_id`, `latitude`,
`longitude`, `country`, and `adm1`. The GADM input must be an EPSG:4326
GeoPackage with an indexed ADM1 layer containing `GID_0`, `COUNTRY`, `GID_1`,
and `NAME_1`; use `--gadm-layer` when it cannot be selected automatically.

`--config harmonize.toml` supplies the same settings; CLI values win. `db`,
`table`, `output`, and `reports_dir` fall back to `[run]` when `[coordinates]`
omits them, so one file can drive both tools.

The coordinate-validation algorithm and its status precedence are specified in
the upstream project, <https://github.com/hhandika/col-taxonomy>.
