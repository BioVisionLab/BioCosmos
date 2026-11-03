# geoharmonize

Validate occurrence coordinates against [GADM](https://gadm.org) administrative boundaries.

- `geoharmonize validate` opens the source DuckDB database read-only and writes a standalone report database.
- `geoharmonize integrate` runs the same validation and also writes the per-record results into a table in the source DuckDB database.

## Usage

Run from the repository root with the backend stopped:

```bash
# Write a starter harmonize.toml configuration file
uv run geoharmonize init

# Inspect tables and column mappings
uv run geoharmonize inspect --db occurrences.duckdb --list-tables
uv run geoharmonize inspect --db occurrences.duckdb --table main.occurrence

# Run read-only validation and write artifacts under reports/geography/<run_id>/
uv run geoharmonize validate --db occurrences.duckdb \
  --table main.occurrence --gadm gadm_410-levels.gpkg --reports-dir reports
```

Each run writes `coordinate_validation.duckdb` and `coordinate_run.json` under `<reports-dir>/geography/<run_id>/` and updates `<reports-dir>/latest.json` (see [`reports/README.md`](../../reports/README.md)).

## Inputs and Column Mapping

By default, `geoharmonize` auto-detects Darwin Core columns (`occurrenceID`, `decimalLatitude`, `decimalLongitude`, `countryCode` or `country`, and `stateProvince`). Override any logical field (`source_id`, `latitude`, `longitude`, `country`, `adm1`) with `--map FIELD=COLUMN` or under `[coordinate_columns]` in `harmonize.toml`.

Provide an extracted GADM 4.1 GeoPackage (`gadm_410-levels.gpkg` from the [GADM download page](https://gadm.org/download_country_v4.html)) in EPSG:4326 with an ADM1 layer containing `GID_0`, `COUNTRY`, `GID_1`, and `NAME_1`.

## Integrating with BioCosmos

The backend reads `main.image_meta_coordinates` at startup and does not run GADM geometry checks itself.

1. Start the backend once so `LocalityService` joins `image_meta` and `gbif_meta` into `main.image_meta_locality`, then **stop the backend** (`Ctrl+C`).
2. Verify the locality table and integrate the validated coordinates:

```bash
uv run geoharmonize inspect --db "$DUCK_DIR/biocosmos.duckdb" \
  --table main.image_meta_locality \
  --map source_id=img_id --map country=country_code --map adm1=state_province

uv run geoharmonize integrate --db "$DUCK_DIR/biocosmos.duckdb" \
  --table main.image_meta_locality --gadm "$GADM_DIR/gadm_410-levels.gpkg" \
  --map source_id=img_id --map country=country_code --map adm1=state_province \
  --into main.image_meta_coordinates --reports-dir reports
```

> Always run against `main.image_meta_locality`, not `main.image_meta` (which lacks `country_code` and `state_province`). Pass `--replace` to overwrite an existing `main.image_meta_coordinates` table.

### Integrated Table Schema (`main.image_meta_coordinates`)

| Column | Description |
| :--- | :--- |
| `source_id` | Mapped record key (`img_id`); rows with a null `source_id` are skipped |
| `validation_status` | Final status: `VALID`, `ADM1_MISMATCH`, `COUNTRY_MISMATCH`, `AMBIGUOUS_REFERENCE`, `NO_REFERENCE_MATCH`, `ZERO_COORDINATE`, `COORDINATE_OUT_OF_RANGE`, or `MISSING_COORDINATE` |
| `coordinate_check`, `country_check`, `adm1_check` | Component check outcomes |
| `latitude`, `longitude` | Parsed numeric coordinates (`NULL` if unparseable) |
| `recorded_country`, `recorded_country_code`, `recorded_adm1` | Recorded locality values from the source table |
| `reference_country`, `reference_adm1`, `reference_gid_0`, `reference_gid_1` | Matched GADM administrative region (`NULL` unless a single GADM region matched) |
| `run_id`, `gadm_sha256` | Run identifier and SHA-256 fingerprint of the GADM file |

## Development

```bash
uv run --package geoharmonize pytest packages/geoharmonize/tests -q
uv run ruff check packages/geoharmonize && uv run ruff format --check packages/geoharmonize
```
