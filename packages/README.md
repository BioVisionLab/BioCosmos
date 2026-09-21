# packages/

Offline data-harmonization tools for BioCosmos, imported from
[col-taxonomy](https://github.com/hhandika/col-taxonomy) with its history and
split into three Python packages.

| Package                            | Command        | Purpose                                                    |
| ---------------------------------- | -------------- | ---------------------------------------------------------- |
| [`harmonize-core`](harmonize-core) | —              | Shared DuckDB, config, output, and reporting primitives    |
| [`colharmonize`](colharmonize)     | `colharmonize` | Match occurrence names against a Catalogue of Life release |
| [`geoharmonize`](geoharmonize)     | `geoharmonize` | Validate occurrence coordinates against GADM geography     |

The two tools were one package upstream. They are split here because they share
no domain logic and have disjoint dependencies — `shapely` and `pycountry` for
geography, `matplotlib` and `seaborn` for the taxonomy summary plots.

These are members of the repository-root uv workspace, which also contains
`backend/`. There is one lockfile at the root.

```bash
uv sync --all-packages

uv run colharmonize --help
uv run geoharmonize --help

uv run --package harmonize-core pytest packages/harmonize-core/tests -q
uv run --package colharmonize   pytest packages/colharmonize/tests -q
uv run --package geoharmonize   pytest packages/geoharmonize/tests -q

uv run ruff check packages/ && uv run ruff format --check packages/
```

Both tools write their run artifacts to [`reports/`](../reports), which
documents the manifest contract the backend will consume.

## Relationship to the backend

The packages do not import the backend. The backend does import
`colharmonize`, however: it runs the taxonomy matcher in-process at startup and
writes its application tables directly. Running the `colharmonize` CLI remains
useful for tuning and report exports, but is not required to start the site.

`geoharmonize` remains an offline workflow. After the backend creates
`main.image_meta_locality`, stop the backend and run `geoharmonize integrate`
to write `main.image_meta_coordinates`. See [`reports/README.md`](../reports/README.md)
for the complete workflow and the CLI artifact contract.
