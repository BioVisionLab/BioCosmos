# harmonize-core

Shared building blocks for the BioCosmos harmonization tools,
[`colharmonize`](../colharmonize) and [`geoharmonize`](../geoharmonize). It is a
library only — it installs no command.

It exists because the two tools grew from one codebase and still share the parts
that are not domain specific:

| Module | Purpose |
| --- | --- |
| `errors` | `HarmonizeError` and the `ConfigurationError` / `SourceValidationError` / `OutputError` hierarchy both CLIs map to exit code 2 |
| `identifiers` | Safe DuckDB identifier parsing and quoting |
| `models` | `FrozenModel`, `ProjectConfigBase`, catalog models, and `ArtifactDigest` |
| `sources` | `DuckDBCatalog` and `OccurrenceSource`, plus the column-resolution primitives each tool specializes |
| `outputs` | `ArtifactRepository`: atomic DuckDB and manifest writes, and SHA-256 digests of finished artifacts |
| `config` | Shared TOML loading, `FIELD=COLUMN` mapping parsing, and CLI-over-TOML override merging |
| `progress` | `RunReporter`, the staged progress display with elapsed and estimated remaining time |
| `reports` | The `reports/` directory layout and the `latest.json` pointer file |

## Why one configuration file works for both tools

`ProjectConfigBase` ignores unknown top-level tables while each table keeps
strict key validation. `colharmonize` reads `[run]`, `[columns]`, and
`[matching]`; `geoharmonize` reads `[coordinates]`, `[coordinate_columns]`, and
the shared keys of `[run]`. Either tool can therefore be pointed at the same
`harmonize.toml` and will ignore the other's sections, while still rejecting a
misspelled key inside a section it owns.
