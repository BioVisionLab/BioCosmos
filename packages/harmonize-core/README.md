# harmonize-core

Shared DuckDB catalog access, TOML configuration, country and place-name normalization, and artifact reporting for [`colharmonize`](../colharmonize/README.md), [`geoharmonize`](../geoharmonize/README.md), the backend, and the analysis notebooks. This is an internal library with no CLI.

## Modules

| Module | Purpose |
| :--- | :--- |
| `config` | TOML configuration loading, `FIELD=COLUMN` mapping parser, and CLI override merging |
| `countries` | Country name and code normalization (`data/country_locations.csv`), sovereign-parent mapping, and Natural Earth 1:110m map markers |
| `places` | Accent-insensitive geographic (`normalize_geographic_name`) and ADM1 (`normalize_adm1`) name normalization shared by `geoharmonize` and backend locality queries |
| `errors` | `HarmonizeError` hierarchy (`ConfigurationError`, `SourceValidationError`, `OutputError`), reported by CLIs with exit code `2` |
| `identifiers` | Safe DuckDB schema/table/column identifier validation and quoting |
| `models` | `FrozenModel`, `ProjectConfigBase`, `TableIdentifier`, `CatalogTable`, `CatalogColumn`, and `ArtifactDigest` |
| `sources` | `DuckDBCatalog`, `OccurrenceSource`, and automatic Darwin Core column detection |
| `outputs` | `ArtifactRepository`: atomic DuckDB/JSON writes and SHA-256 artifact digests |
| `progress` | `RunReporter`: stage progress reporting with elapsed time and ETA |
| `reports` | Standard `reports/<domain>/<run_id>/` directory layout and `reports/latest.json` pointer updates |

## Shared TOML Configuration

`ProjectConfigBase` ignores unknown top-level TOML tables while enforcing strict key validation inside each tool's own sections:

- `colharmonize` reads `[run]`, `[columns]`, and `[matching]`.
- `geoharmonize` reads `[coordinates]`, `[coordinate_columns]`, and the shared keys of `[run]` (`db`, `table`, `output`, `reports_dir`).

Because each tool ignores the other's sections, a single `harmonize.toml` file can configure both tools.

## Country and Place Normalization

- `countries` resolves country names, ISO 3166-1 alpha-2/alpha-3 codes, and GADM references using the bundled `data/country_locations.csv` table, and supplies coordinates for small island territories absent from coarse 1:110m basemaps (see [`analyses/data/README.md`](../../analyses/data/README.md)).
- `places` strips accents, punctuation, and generic administrative terms (`state`, `province`, `department`, `prefecture`, `oblast`, etc.) so ADM1 names validated offline by `geoharmonize` match the same way at query time in the backend.

## Development

```bash
uv run --package harmonize-core pytest packages/harmonize-core/tests -q
uv run ruff check packages/harmonize-core && uv run ruff format --check packages/harmonize-core
```
