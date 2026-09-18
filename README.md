# colharmonize

`colharmonize` pre-generates compact, auditable species-name matches against a Catalogue of Life ColDP release.

```bash
uv sync
uv run colharmonize init
uv run colharmonize inspect --db occurrences.duckdb --list-tables
uv run colharmonize inspect --db occurrences.duckdb --list-columns main.occurrence
uv run colharmonize inspect --db occurrences.duckdb --table main.occurrence \
  --map scientific_name=species
uv run colharmonize run --db occurrences.duckdb --table main.occurrence \
  --map scientific_name=species --col NameUsage.tsv --output results --csv --plot
```

Use `--config colharmonize.toml` with `inspect`, `index`, or `run`. CLI values override TOML. Run `colharmonize init --output -` to inspect the complete configuration template.

## Matching workflow

```mermaid
flowchart LR
    OCC[(Occurrence DuckDB)] -->|read only| INSPECT[Validate table and map columns]
    INSPECT --> DISTINCT[Extract distinct taxonomy variants]
    DISTINCT --> NORMALIZE[Normalize binomials and create input_taxon_key]

    COL[CoL archive or NameUsage file] --> HASH[Calculate SHA-256]
    HASH --> CACHE{Cached index exists?}
    CACHE -->|Yes| INDEX[(Reference index)]
    CACHE -->|No| BUILD[Build accepted, usage, synonym, and family lookups]
    BUILD --> INDEX

    NORMALIZE --> MATCH[Generate candidate evidence]
    INDEX --> MATCH
    MATCH --> RESOLVE[Collapse by accepted CoL taxon ID and rank]
    RESOLVE --> OUTPUT[(taxonomy_update.duckdb)]
    OUTPUT --> MANIFEST[run.json]
    OUTPUT --> CSV[taxonomy_summary.csv]
    OUTPUT --> PLOT[taxonomy_match_summary.png]
    OUTPUT -. opt-in write-back .-> LOOKUP[(Compact lookup in occurrence DuckDB)]
```

Candidate methods run as a union rather than as a first-match-wins sequence:

```mermaid
flowchart TB
    INPUT[Normalized species-level input] --> VALID{Valid binomial and rank?}
    VALID -->|No| UNMATCHED[UNMATCHED with reason code]
    VALID -->|Yes| EA[Exact accepted usage]
    VALID -->|Yes| ES[Exact synonym usage]
    VALID -->|Yes| EC[Exact canonical binomial]
    VALID -->|Yes| FE[Family and exact epithet]
    VALID -->|Yes| SG[Genus spelling candidate]
    VALID -->|Yes| SE[Epithet spelling candidate]
    VALID -->|Yes| FT[Family-restricted fuzzy typo]

    EA --> UNION[Union candidate evidence]
    ES --> UNION
    EC --> UNION
    FE --> UNION
    SG --> UNION
    SE --> UNION
    FT --> UNION

    UNION --> COLLAPSE[Collapse usages by accepted taxon ID]
    COLLAPSE --> SCORE[Apply deterministic evidence score]
    SCORE --> RANK[Retain top-k plus runner-up and score margin]
    RANK --> FOUND{Any candidate?}
    FOUND -->|No| UNMATCHED
    FOUND -->|Yes| CLEAR{Unique or clearly separated evidence?}
    CLEAR -->|Yes| MATCHED[MATCHED]
    CLEAR -->|No| AMBIGUOUS[AMBIGUOUS with best candidate retained]
```

The primary artifact is `taxonomy_update.duckdb`. It contains `input_taxa`, `input_taxon_variants`, `taxonomy_matches`, `taxonomy_candidates`, `summary_metrics`, and `run_metadata`. Scores are deterministic evidence scores, not probabilities.

To copy a compact lookup into the source database, add `--write-back-table main.taxonomy_lookup`. This opt-in operation creates a new table and fails if that table already exists.

Join an external result by the original source fields:

```sql
ATTACH 'results/taxonomy_update.duckdb' AS harmonized;
SELECT occurrence.*, matches.accepted_name, matches.update_status
FROM occurrence
LEFT JOIN harmonized.input_taxon_variants variants
  ON occurrence.species = variants.original_scientific_name
 AND occurrence.family IS NOT DISTINCT FROM variants.original_family
LEFT JOIN harmonized.taxonomy_matches matches USING (input_taxon_key);
```

Only species-level binomials are matched. Ambiguous and unmatched inputs remain explicit; no interactive review or overrides are performed.
