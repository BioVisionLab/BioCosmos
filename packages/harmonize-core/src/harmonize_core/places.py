"""Place-name normalization shared by the harmonizers and the backend.

geoharmonize compares recorded ADM1 names against GADM with these, and the
backend's locality filter matches a requested state or province the same way,
so a name that validates offline also matches at query time.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache

_ADMIN_WORDS = re.compile(
    r"\b(?:state|province|region|department|district|county|territory|governorate|prefecture|"
    r"oblast|municipality)\b",
    re.IGNORECASE,
)


def strip_accents(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )


# geoharmonize runs these as DuckDB scalar functions, once per occurrence row.
# Their domain is the set of distinct recorded place names, and both are pure,
# so caching turns most of those calls into a dict lookup.
@cache
def normalize_geographic_name(value: str | None) -> str | None:
    """Normalize a geographic name for punctuation-insensitive comparison."""
    if value is None or not value.strip():
        return None
    return re.sub(r"[^a-z0-9]+", "", strip_accents(value).casefold()) or None


@cache
def normalize_adm1(value: str | None) -> str | None:
    """Normalize ADM1 names while removing generic administrative words."""
    if value is None or not value.strip():
        return None
    without_admin_words = _ADMIN_WORDS.sub(" ", strip_accents(value).casefold())
    return re.sub(r"[^a-z0-9]+", "", without_admin_words) or None
