# instharmonize

Resolve occurrence `institutionCode` values (such as `MCZ`, `NHMUK`, or `ZRC`) to full institution names and homepages using two public GBIF registries: [GRSciColl](https://scientific-collections.gbif.org) for scientific collections and the GBIF organization registry for dataset publishers.

## Usage

Run from the repository root (stop the backend first if reading from its live DuckDB file):

```bash
# Look up a single institution code
uv run instharmonize lookup MCZ
uv run instharmonize lookup TU --dataset-key 2b044aa9-1a9a-413e-8b18-ed09da575d3f

# Resolve all institution codes in a GBIF TSV or DuckDB table
uv run instharmonize resolve gbif-occurrence.tsv -o institutions.csv
uv run instharmonize resolve "$DUCK_DIR/biocosmos.duckdb" --table gbif_meta -o institutions.csv
```

## How Resolution Works

Museum and university acronyms are often shared across unrelated institutions (for example, `KSU` can refer to Kansas State University or King Saud University). Rather than looking up a code in isolation, `instharmonize` uses the GBIF dataset metadata associated with each occurrence and evaluates evidence in priority order:

| `source` | How the institution was resolved |
| :--- | :--- |
| `curated` | Matched a manually verified entry in `resources/overrides.toml` (or `--overrides FILE`) |
| `verbatim` | The recorded code or `institutionID` already contains a full institution name (e.g., `"Naturalis Biodiversity Center"`) |
| `grscicoll_exact` | GRSciColl's dataset-aware occurrence lookup returned an exact match (such as a ROR or GRSciColl `institutionID`) |
| `grscicoll_verified` | A GRSciColl institution with that code whose name agrees with the dataset's publishing organization |
| `gbif_publisher` | The dataset's GBIF publisher name expands the acronym (e.g., `"Kansas State University …"` for `KSU`) |
| `unresolved` | No reliable match found; the raw code is kept as-is |

## Curated Overrides

[`src/instharmonize/resources/overrides.toml`](src/instharmonize/resources/overrides.toml) stores manually verified mappings for codes that public registries cannot disambiguate. Pass `--overrides FILE` to supply additional entries:

```toml
[institutions.TU]
use_publisher = true   # Use the GBIF dataset publisher as the holding institution

[institutions.PU]
name = "Purdue Entomological Research Collection"
homepage = "https://..."
```

## Backend Integration

The backend imports `instharmonize` at startup, resolves the institution codes present in the collection, and stores the results in `institution_directory` (used by the Institutions page and specimen provenance queries). Resolved entries are cached in DuckDB so subsequent startups do not repeat GBIF network calls unless `RESOLVER_VERSION` or `overrides.toml` changes.

## Development

```bash
uv run --package instharmonize pytest packages/instharmonize/tests -q
uv run ruff check packages/instharmonize && uv run ruff format --check packages/instharmonize
```
