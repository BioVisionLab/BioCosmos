# harmonize-core

Shared database access, configuration, and reporting for
[`colharmonize`](../colharmonize/README.md) and
[`geoharmonize`](../geoharmonize/README.md). This is a library; it has no CLI.

The tools share these modules while keeping taxonomy matching and coordinate
validation in their own packages:

| Module        | Purpose                                                                                                                                    |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `errors`      | `HarmonizeError` and its subclasses (`ConfigurationError`, `SourceValidationError`, `OutputError`), reported by both CLIs with exit code 2 |
| `identifiers` | Safe DuckDB identifier parsing and quoting                                                                                                 |
| `models`      | `FrozenModel`, `ProjectConfigBase`, catalog models, and `ArtifactDigest`                                                                   |
| `sources`     | `DuckDBCatalog`, `OccurrenceSource`, and column-resolution helpers used by each tool                                                       |
| `outputs`     | `ArtifactRepository`: atomic DuckDB and manifest writes, and SHA-256 digests of finished artifacts                                         |
| `config`      | TOML loading, `FIELD=COLUMN` parsing, and merging settings with CLI values taking precedence                                               |
| `progress`    | `RunReporter`: progress by stage, with elapsed time and estimated time remaining                                                           |
| `reports`     | The `reports/` directory layout and the `latest.json` pointer file                                                                         |

## Shared configuration

`ProjectConfigBase` ignores unknown top-level tables while each table keeps
strict key validation. `colharmonize` reads `[run]`, `[columns]`, and
`[matching]`; `geoharmonize` reads `[coordinates]`, `[coordinate_columns]`, and
the shared keys of `[run]`. Both tools can use the same `harmonize.toml`. Each
ignores the other tool's sections and rejects unknown keys in its own sections.

## Country mapping

`countries` normalizes country codes and names using the bundled
`data/country_locations.csv`. The backend and publication notebooks use the same
table for country labels and map markers. See the
[analysis data README](../../analyses/data/README.md) for sources and
normalization rules.

## Development

```bash
uv run --package harmonize-core pytest packages/harmonize-core/tests -q
```
