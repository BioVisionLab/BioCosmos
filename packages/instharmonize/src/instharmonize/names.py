"""Comparing institution codes and names without a registry.

A code search in GRSciColl is only a hint: `KSU` finds King Saud University
for a Kansas State dataset, and `UI` finds the Bureau of Land Management for a
University of Idaho one. These helpers decide whether a candidate name agrees
with what the occurrence data itself says about its source.
"""

from __future__ import annotations

import re
import unicodedata

# Words that carry no identity in an institution name. Generic nouns such as
# "museum" and "university" are kept: "Natural History Museum" matching
# "Natural History Museum, London" should count.
_STOPWORDS = frozenset(
    {
        "a",
        "and",
        "at",
        "da",
        "das",
        "de",
        "del",
        "della",
        "der",
        "des",
        "di",
        "die",
        "do",
        "du",
        "e",
        "et",
        "fur",
        "in",
        "la",
        "le",
        "les",
        "of",
        "the",
        "und",
        "y",
    }
)

# Codes the data uses to mean "no code".
_PLACEHOLDER_CODES = frozenset({"", "-", "--", "na", "n/a", "none", "null", "unknown"})

_TRAILING_ABBREVIATION = re.compile(r"^(?P<name>.+?)\s*\((?P<code>[^()]+)\)\s*$")


def fold(text: str) -> str:
    """Lowercase and strip accents, so "Zoología" compares equal to "zoologia"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(text))


def name_tokens(name: str) -> frozenset[str]:
    """The identifying words of a name, for set comparison."""
    return frozenset(w for w in _words(name) if w not in _STOPWORDS and len(w) > 1)


def name_similarity(first: str, second: str) -> float:
    """Overlap coefficient of the two names' identifying words.

    Scored against the shorter name, because a registry name and a publisher
    name routinely differ by a qualifier ("..., London", "..., C.P. Gillette
    Museum of Arthropod Diversity"). A single shared word is not evidence --
    "University" alone would pair any two universities -- unless one name is
    a single word.
    """
    a, b = name_tokens(first), name_tokens(second)
    if not a or not b:
        return 0.0
    shared = a & b
    if len(shared) < 2 and min(len(a), len(b)) > 1:
        return 0.0
    return len(shared) / min(len(a), len(b))


def code_matches_name(code: str, name: str) -> bool:
    """Whether a name plausibly expands an abbreviation.

    True when the name contains the code as a word or a word prefix ("WWU" in
    "... Collection (WWUC)"), or when the code's letters appear in order among
    the initials of the name's words, starting at the first significant word
    ("KSU" in "Kansas State University ...", "UI" in "University of Idaho").
    """
    letters = "".join(re.findall(r"[a-z]", fold(code)))
    if len(letters) < 2:
        return False
    words = _words(name)
    if any(len(letters) >= 3 and word.startswith(letters) for word in words):
        return True

    significant = [w for w in words if w not in _STOPWORDS]
    if not significant or significant[0][0] != letters[0]:
        return False
    initials = iter(w[0] for w in words)
    return all(letter in initials for letter in letters)


def is_placeholder_code(code: str | None) -> bool:
    return code is None or code.strip().lower() in _PLACEHOLDER_CODES


def split_verbatim_name(code: str) -> tuple[str, str | None] | None:
    """Recognize a full name written where the code belongs.

    Returns (name, abbreviation) for values such as "Hartland Nature Club" or
    "Universitas Cenderawasih (UNCEN)", and None for an ordinary code. A value
    counts as a name when it has at least two words and some lowercase letters;
    codes are short and usually capitalized ("MCZ", "SMNH-NASU", "tesri").
    """
    value = " ".join(code.split())
    words = value.split(" ")
    if len(words) < 2 or not any(c.islower() for c in value):
        return None
    match = _TRAILING_ABBREVIATION.match(value)
    if match:
        return match.group("name"), match.group("code").strip()
    return value, None
