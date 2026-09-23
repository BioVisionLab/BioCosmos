# instharmonize

Resolves occurrence `institutionCode` abbreviations (`MCZ`, `NHMUK`, `ZRC`) to
the institution's full name and website. It uses two public GBIF registries:
[GRSciColl](https://scientific-collections.gbif.org) for institutions, and the
GBIF organization registry for dataset publishers.

```bash
uv run instharmonize lookup MCZ
uv run instharmonize lookup TU --dataset-key 2b044aa9-1a9a-413e-8b18-ed09da575d3f
uv run instharmonize resolve gbif-occurrence.tsv -o institutions.csv
uv run instharmonize resolve occurrences.duckdb --table gbif_meta -o institutions.csv
```

`resolve` reads a GBIF occurrence download, or a DuckDB table with the same
columns, read-only. It needs `institutionCode` and uses `datasetKey`,
`institutionID`, `ownerInstitutionCode`, `publisher`, and `publishingCountry`
when the source has them. It writes one CSV row per code with `code`, `name`,
`homepage`, `country`, `grscicoll_key`, `source`, and `occurrences`.

## Why the dataset matters

Codes are not unique. GRSciColl lists four institutions under `TU`, and none of
them is the University of Tartu, which publishes this data as `TU`. A bare code
search maps `KSU` to King Saud University and `UI` to the Bureau of Land
Management, when the records come from Kansas State and the University of
Idaho. Each code is therefore resolved in the context of the datasets it
appears in. The strongest evidence wins:

| `source`             | Evidence                                                                                                    |
| -------------------- | ----------------------------------------------------------------------------------------------------------- |
| `curated`            | An entry in the overrides file                                                                              |
| `verbatim`           | The code field, or an `institutionID` standing in for a blank code, holds a name ("Naturalis Biodiversity Center") |
| `grscicoll_exact`    | GRSciColl's dataset-aware lookup matched exactly, e.g. on a ROR or GRSciColl `institutionID`                |
| `grscicoll_verified` | A GRSciColl institution with that code whose name agrees with the dataset's publisher                       |
| `gbif_publisher`     | The dataset's GBIF publisher, when its name spells out the code ("Kansas State University …" for `KSU`)     |
| `unresolved`         | None of the above; the code is shown as-is                                                                  |

A publisher that publishes several codes, such as a national biodiversity
portal, is treated as an aggregator. Its name is not used as evidence. In its
place, a single GRSciColl candidate in the publisher's country is accepted.

The homepage is GRSciColl's. When GRSciColl has none, the publisher's is used,
but only if the two names agree.

## Overrides

[`resources/overrides.toml`](src/instharmonize/resources/overrides.toml) holds
hand-checked codes the registries cannot settle, and `--overrides FILE` layers
another file on top:

```toml
[institutions.TU]
use_publisher = true   # the publisher is the holding institution

[institutions.PU]
name = "Purdue Entomological Research Collection"
homepage = "https://..."
```

## In BioCosmos

The backend imports the resolver and runs it at startup against the codes
behind the collection's images. The results go into the
`institution_directory` table, and the collection's Institutions page reads
it. Only codes that are not yet in the table are sent to GBIF. A change to the
rules (`RESOLVER_VERSION`) or to the overrides re-resolves every code. A code
that failed on a network error is retried at the next start.

```bash
uv run --package instharmonize pytest packages/instharmonize/tests -q
```
