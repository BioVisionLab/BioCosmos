# geoharmonize

Validates occurrence coordinates against [GADM](https://gadm.org) administrative geography.
`validate` reads the occurrence DuckDB read-only and never modifies it;
`integrate` additionally writes the result back as a new table.

```bash
uv run geoharmonize init
uv run geoharmonize inspect --db occurrences.duckdb --list-tables
uv run geoharmonize validate --db occurrences.duckdb \
  --table main.occurrence --gadm gadm.gpkg --reports-dir reports
```

Writes `coordinate_validation.duckdb` and `coordinate_run.json`. With
`--reports-dir` they land in `<reports-dir>/geography/<run_id>/` and
`latest.json` is updated to point at the run; `--output` writes to an explicit
directory instead. See [`reports/`](../../reports) for the artifact contract.

Detects the Darwin Core fields `occurrenceID`, `decimalLatitude`,
`decimalLongitude`, `countryCode` or `country`, and `stateProvince`. Override
one with `--map FIELD=COLUMN`; the logical fields are `source_id`, `latitude`,
`longitude`, `country`, and `adm1`.

The GADM input must be an EPSG:4326
GeoPackage with an indexed ADM1 layer containing `GID_0`, `COUNTRY`, `GID_1`,
and `NAME_1`; use `--gadm-layer` when it cannot be selected automatically. Download the latest GADM 410 release (six separate layers (one for each level of subdivision/aggregation)) from <https://gadm.org/download_country_v4.html>. Extract the `gadm_410-levels.gpkg` file and point to it with `--gadm`.

`--config harmonize.toml` supplies the same settings; CLI values win. `db`,
`table`, `output`, and `reports_dir` fall back to `[run]` when `[coordinates]`
omits them, so one file can drive both tools.

The coordinate-validation algorithm and its status precedence are specified in
the upstream project, <https://github.com/hhandika/col-taxonomy>.

## integrate

`integrate` runs the same validation and then writes it into the **occurrence**
database, rather than only under `reports/`:

For BioCosmos, first start the backend and wait for it to build
`main.image_meta_locality` from `image_meta` and `gbif_meta`. Stop the backend,
then verify the derived source before integrating:

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

**Stop anything else using the database first.** DuckDB allows a single writer,
and `integrate` needs the file read-write.

Do not use `main.image_meta` with the locality mappings above. That raw table
has `img_id`, `lat`, and `lon`, but `country_code` and `state_province` only
become available after the backend creates `main.image_meta_locality`.

The destination holds one row per occurrence, keyed on the mapped `source_id`,
so it joins straight back to the table it was read from:

| Column | Meaning |
| --- | --- |
| `source_id` | The mapped key; rows without one are skipped |
| `validation_status` | The final outcome, one of eight values |
| `coordinate_check`, `country_check`, `adm1_check` | The component checks behind it |
| `latitude`, `longitude` | The parsed coordinate, null where it could not be read |
| `recorded_country`, `recorded_country_code`, `recorded_adm1` | What the occurrence recorded |
| `reference_country`, `reference_adm1`, `reference_gid_0`, `reference_gid_1` | What GADM says is there |
| `run_id`, `gadm_sha256` | Which run produced the row, and from which GADM file |

The `reference_*` columns are **null unless exactly one GADM region matched**, so
a reader must consult `validation_status` to tell `NO_REFERENCE_MATCH` from
`AMBIGUOUS_REFERENCE` rather than reading a null as "outside every country".

`integrate` refuses an existing destination; pass `--replace` to rebuild one. It
also refuses to write into the table it is reading, and refuses to run at all
when no `source_id` column resolves — a table keyed on nothing is useless to
every consumer, and both failures are cheaper to hit before the run than after.

`validate` never writes back, even when `write_back_table` is set in the TOML.
The command name is the contract.
