# instharmonize

Resolve occurrence `institutionCode` abbreviations such as `MCZ`, `NHMUK`, and
`ZRC` to institution names and websites. The resolver uses two public GBIF
registries: [GRSciColl](https://scientific-collections.gbif.org) for
institutions, and the GBIF organization registry for dataset publishers.

## Usage

Run from the repository root. Stop the backend before resolving records from its
live DuckDB file.

```bash
uv run instharmonize lookup MCZ
uv run instharmonize lookup TU --dataset-key 2b044aa9-1a9a-413e-8b18-ed09da575d3f
uv run instharmonize resolve gbif-occurrence.tsv -o institutions.csv
uv run instharmonize resolve occurrences.duckdb --table gbif_meta -o institutions.csv
```

## How resolution works

Institution codes are not unique. A code-only lookup can assign records to the
wrong institution: `KSU` can refer to King Saud University or Kansas State
University, for example. The resolver uses the datasets associated with each
code to decide which institution it represents, in this order:

| `source`             | Evidence                                                                                                           |
| -------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `curated`            | An entry in the overrides file                                                                                     |
| `verbatim`           | The code field, or an `institutionID` standing in for a blank code, holds a name ("Naturalis Biodiversity Center") |
| `grscicoll_exact`    | GRSciColl's dataset-aware lookup matched exactly, e.g. on a ROR or GRSciColl `institutionID`                       |
| `grscicoll_verified` | A GRSciColl institution with that code whose name agrees with the dataset's publisher                              |
| `gbif_publisher`     | The dataset's GBIF publisher, when its name spells out the code ("Kansas State University …" for `KSU`)            |
| `unresolved`         | None of the above; the code is shown as-is                                                                         |

## Overrides

[`resources/overrides.toml`](src/instharmonize/resources/overrides.toml) holds
manually checked codes the registries cannot resolve. Use `--overrides FILE` to
add or replace entries:

```toml
[institutions.TU]
use_publisher = true   # the publisher is the holding institution

[institutions.PU]
name = "Purdue Entomological Research Collection"
homepage = "https://..."
```

## Backend integration

The backend imports the resolver and runs it at startup against the codes
associated with the collection's images. Results are stored in
`institution_directory`, which supplies the Institutions page. Codes with a
cached result do not need another GBIF request. Changes to `RESOLVER_VERSION` or
the overrides trigger resolution of all codes again; network failures are
retried at the next startup.

## Development

```bash
uv run --package instharmonize pytest packages/instharmonize/tests -q
```
