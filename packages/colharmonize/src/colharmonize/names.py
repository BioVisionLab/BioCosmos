"""Shared SQL parsing for optional subspecies epithets."""


def subspecies_epithet_sql(name: str, authorship: str) -> str:
    """Parse lowercase third epithets, preserving case to exclude author surnames.

    Strip supplied authorship first. Rank markers are accepted, while an unmarked
    epithet must be lowercase in the source (before name normalization).
    """
    return rf"""nullif(regexp_extract(
        regexp_replace(
            CASE WHEN nullif(trim({authorship}), '') IS NOT NULL
                 AND ends_with(trim({name}), trim({authorship}))
                 THEN left(trim({name}), length(trim({name})) - length(trim({authorship})))
                 ELSE {name} END,
            '\s*\([^)]+\)\s*', ' ', 'g'),
        '^\s*[^ ]+\s+[[:lower:]×-]+\s+(?:(?:subsp\.|ssp\.)\s+)?([[:lower:]×-]+)(?:\s|$)',
        1), '')"""
