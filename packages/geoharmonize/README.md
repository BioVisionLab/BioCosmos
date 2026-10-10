# geoharmonize

Validate occurrence coordinates against [GADM](https://gadm.org) administrative
geography. `validate` reads the source DuckDB read-only and saves a report.
`integrate` runs the same validation and also writes the results into the source
database as a new table.

## Usage

Run from the repository root. Stop the backend before either command accesses
its live DuckDB file.

```bash
uv run geoharmonize init
uv run geoharmonize inspect --db occurrences.duckdb --list-tables
uv run geoharmonize validate --db occurrences.duckdb \
  --table main.occurrence --gadm gadm.gpkg --reports-dir reports
```

Each run writes `coordinate_validation.duckdb` and `coordinate_run.json`. With
`--reports-dir`, outputs go to `<reports-dir>/geography/<run_id>/` and
`latest.json` points to the run. Use `--output` to choose an explicit directory.
See the [report format](../../reports/README.md).

## Inputs and configuration

The tool detects the Darwin Core fields `occurrenceID`, `decimalLatitude`,
`decimalLongitude`, `countryCode` or `country`, and `stateProvince`. Override
one with `--map FIELD=COLUMN`; the logical fields are `source_id`, `latitude`,
`longitude`, `country`, and `adm1`.

Use a GADM GeoPackage in EPSG:4326 with an indexed ADM1 layer containing
`GID_0`, `COUNTRY`, `GID_1`, and `NAME_1`. Pass `--gadm-layer` if the tool
cannot select the layer automatically. For the BioCosmos workflow, use the GADM
4.1 file `gadm_410-levels.gpkg`, which contains a separate layer for each
administrative level. Point `--gadm` at the extracted file. See the
[GADM download page](https://gadm.org/download_country_v4.html).

Use `--config harmonize.toml` to read settings from a file. CLI values take
precedence. `db`, `table`, `output`, and `reports_dir` fall back to `[run]` when
`[coordinates]` omits them, so one file can drive both tools.

The [upstream project](https://github.com/hhandika/col-taxonomy) documents the
validation algorithm and status precedence.

## Integrate with BioCosmos

The backend reads the integrated coordinate table; it does not run coordinate
validation at startup.

Export `$DUCK_DIR` and `$GADM_DIR` in your shell. Start the backend and wait for
it to build `main.image_meta_locality` from `image_meta` and `gbif_meta`. Stop
the backend, then verify the derived source before integrating:

```bash
uv run geoharmonize inspect --db "$DUCK_DIR/biocosmos.duckdb" \
  --list-columns main.image_meta_locality
uv run geoharmonize inspect --db "$DUCK_DIR/biocosmos.duckdb" \
  --table main.image_meta_locality \
  --map source_id=img_id --map country=country_code --map adm1=state_province
```

```bash
uv run geoharmonize integrate --db "$DUCK_DIR/biocosmos.duckdb" \
  --table main.image_meta_locality --gadm "$GADM_DIR/gadm_410-levels.gpkg" \
  --map source_id=img_id --map country=country_code --map adm1=state_province \
  --into main.image_meta_coordinates --reports-dir reports
```

Keep the backend stopped until integration finishes. DuckDB allows a single
writer, and `integrate` opens the file read-write.

Use `main.image_meta_locality` with these mappings. The filtered `image_meta`
view has `img_id`, `lat`, and `lon`; `country_code` and `state_province` become
available in the derived locality table.

### Integrated table

The destination holds one row per occurrence, keyed on the mapped `source_id`,
so results join directly to the source table:

| Column                                                                      | Meaning                                                |
| --------------------------------------------------------------------------- | ------------------------------------------------------ |
| `source_id`                                                                 | The mapped key; rows without one are skipped           |
| `validation_status`                                                         | The final outcome, one of eight values                 |
| `coordinate_check`, `country_check`, `adm1_check`                           | The component checks behind it                         |
| `latitude`, `longitude`                                                     | The parsed coordinate, null where it could not be read |
| `recorded_country`, `recorded_country_code`, `recorded_adm1`                | Recorded locality fields                               |
| `reference_country`, `reference_adm1`, `reference_gid_0`, `reference_gid_1` | Matched GADM region                                    |
| `run_id`, `gadm_sha256`                                                     | Run ID and GADM input fingerprint                      |

The `reference_*` columns are null unless exactly one GADM region matched. Check
`validation_status` to distinguish `NO_REFERENCE_MATCH` from
`AMBIGUOUS_REFERENCE`; a null alone does not mean the coordinate is outside
every country.

`integrate` fails if the destination exists; pass `--replace` to rebuild it. It
also rejects a destination that is the source table, or an input without a
resolved `source_id` column. These checks happen before validation begins.

`validate` never writes back, even when `write_back_table` is set in the TOML.

## Development

```bash
uv run --package geoharmonize pytest packages/geoharmonize/tests -q
```
