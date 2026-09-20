"""Human-readable descriptions for CoL taxonomic-update codes.

The authoritative descriptions live on the ``UpdateStatus`` and ``MatchMethod``
StrEnums in ``colharmonize.models``.
"""

import logging

logger = logging.getLogger(__name__)

# Mirrors colharmonize.models.UpdateStatus.description.
UPDATE_STATUS_DESCRIPTIONS: dict[str, str] = {
    "MATCHED": "One accepted taxon was resolved with sufficient evidence.",
    "AMBIGUOUS": (
        "Candidates were found, but the evidence did not identify one accepted taxon."
    ),
    "UNMATCHED": (
        "No eligible accepted taxon was found, or the input was invalid or unsupported."
    ),
}

# Mirrors colharmonize.models.MatchMethod.description.
MATCH_METHOD_DESCRIPTIONS: dict[str, str] = {
    "EXACT_ACCEPTED": "The normalized input name exactly matched an accepted name usage.",
    "EXACT_SYNONYM": (
        "The normalized input name exactly matched a synonym of the accepted taxon."
    ),
    "EXACT_CANONICAL": (
        "The parsed genus and epithet exactly matched an accepted canonical binomial."
    ),
    "UNIQUE_FAMILY_EPITHET": (
        "One accepted taxon matched the input family and specific epithet."
    ),
    "SPELLING_GENUS": (
        "The family and epithet matched while genus spelling similarity resolved the taxon."
    ),
    "SPELLING_EPITHET": (
        "The family and genus matched while epithet edit distance resolved the taxon."
    ),
    "FUZZY_TYPO": "Family-restricted spelling similarity resolved both genus and epithet.",
    "AMBIGUOUS": "Candidate evidence did not clearly separate one accepted taxon.",
    "UNMATCHED": "No candidate was found, or the input binomial or rank was unsupported.",
}

# colharmonize cascades species -> subspecies -> genus, prefixing the method
# with the stage that finally resolved it.
RANK_PREFIX_NOTES: dict[str, str] = {
    "SUBSPECIES": "The species-rank pass found nothing, so the match was made at subspecies rank.",
    "GENUS": "The species-rank pass found nothing, so the match resolved only to genus.",
}

# Set on inputs colharmonize declined to match at all (see its pipeline).
REASON_CODE_DESCRIPTIONS: dict[str, str] = {
    "UNSUPPORTED_RANK": (
        "The recorded rank is not one of species, subspecies, or genus, "
        "so the name was not matched."
    ),
    "INVALID_BINOMIAL": (
        "The recorded name could not be parsed as a usable binomial, "
        "so the name was not matched."
    ),
}


def split_match_method(code: str) -> tuple[str | None, str | None]:
    """Split a method code into its rank prefix and base method.

    Returns ``(prefix, base)``, either of which may be None.

    A prefix is stripped only when the remainder is itself a known method, so
    ``SPELLING_GENUS`` — a real method that happens to end in a rank name — is
    never mistaken for a prefixed code.
    """
    if not code:
        return None, None
    normalized = code.strip().upper()
    if normalized in MATCH_METHOD_DESCRIPTIONS:
        return None, normalized
    for prefix in RANK_PREFIX_NOTES:
        candidate = f"{prefix}_"
        if normalized.startswith(candidate):
            base = normalized[len(candidate) :]
            if base in MATCH_METHOD_DESCRIPTIONS:
                return prefix, base
    return None, None


def describe_update_status(code: str | None) -> str | None:
    """Return the prose for an update status, or None when unrecognized."""
    if not code:
        return None
    return UPDATE_STATUS_DESCRIPTIONS.get(code.strip().upper())


def describe_match_method(code: str | None) -> str | None:
    """Return the prose for a method code, including any rank-cascade note."""
    if not code:
        return None
    prefix, base = split_match_method(code)
    if base is None:
        return None
    description = MATCH_METHOD_DESCRIPTIONS[base]
    if prefix is None:
        return description
    return f"{RANK_PREFIX_NOTES[prefix]} {description}"


def describe_reason_code(code: str | None) -> str | None:
    """Return the prose for an unmatched-input reason code."""
    if not code:
        return None
    return REASON_CODE_DESCRIPTIONS.get(code.strip().upper())


def all_descriptions() -> dict[str, dict[str, str]]:
    """The full code dictionary, as served by GET /taxonomy/codes.

    Method entries are expanded with their rank-prefixed forms so the client
    never has to recombine a prefix with a base description itself.
    """
    methods = dict(MATCH_METHOD_DESCRIPTIONS)
    for prefix, note in RANK_PREFIX_NOTES.items():
        for base, description in MATCH_METHOD_DESCRIPTIONS.items():
            methods[f"{prefix}_{base}"] = f"{note} {description}"
    return {
        "updateStatus": dict(UPDATE_STATUS_DESCRIPTIONS),
        "matchMethod": methods,
        "reasonCode": dict(REASON_CODE_DESCRIPTIONS),
    }
