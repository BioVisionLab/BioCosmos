"""Exact GADM/ISO country normalization shared by the notebooks, the API and the map.

One lookup, so a country's code and display name cannot differ between the
published figure, the `/stats/country` endpoint and the polygons the site
shades. Identifiers and unique names only; no fuzzy matching.
"""

from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

import pycountry

# Basemap polygons that carry no ISO code of their own and whose territory GADM
# records under another country. The polygon is then drawn with that country's
# total, because its records are already counted there; it has no separate total
# of its own. Keyed by the basemap's feature name. N. Cyprus stays unmapped: no
# eligible record resolves to it, so nothing would be drawn either way.
FEATURE_PARENTS = {"somaliland": "SO"}

# Common unambiguous English variants not present in the ISO names.
ENGLISH_VARIANTS = {
    "UK": "GB",
    "USA": "US",
    "South Korea": "KR",
    "North Korea": "KP",
    "Russia": "RU",
    "Vietnam": "VN",
    "Laos": "LA",
    "Ivory Coast": "CI",
}

LOCATIONS_RESOURCE = "data/country_locations.csv"


def clean(value: Any) -> str:
    # NaN is the one value unequal to itself; callers pass pandas cells too.
    if value is None or value != value:
        return ""
    return str(value).strip()


def name_key(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", clean(value)).casefold().split())


@dataclass(frozen=True)
class CountryLocation:
    country_code: str
    country_name: str
    longitude: float
    latitude: float
    source: str
    source_feature: str
    aliases: str


def load_locations() -> dict[str, CountryLocation]:
    """One Natural Earth label location per ISO 3166-1 code, plus Kosovo."""
    text = files("harmonize_core").joinpath(LOCATIONS_RESOURCE).read_text(encoding="utf-8")
    locations: dict[str, CountryLocation] = {}
    for row in csv.DictReader(text.splitlines()):
        code = row["country_code"]
        if code in locations:
            raise ValueError(f"Country location lookup contains duplicate code {code!r}.")
        locations[code] = CountryLocation(
            country_code=code,
            country_name=row["country_name"],
            longitude=float(row["longitude"]),
            latitude=float(row["latitude"]),
            source=row["source"],
            source_feature=row["source_feature"],
            aliases=row["aliases"],
        )
    return locations


class CountryLookup:
    """Exact identifiers and unique names only; no fuzzy matching."""

    def __init__(self) -> None:
        self.by_code = load_locations()
        self.aliases = {"UK": "GB", "EL": "GR"}
        names: dict[str, set[str]] = {}
        for country in pycountry.countries:
            for field in ("name", "official_name", "common_name"):
                value = getattr(country, field, None)
                if value:
                    names.setdefault(name_key(value), set()).add(country.alpha_2)
        for code, location in self.by_code.items():
            names.setdefault(name_key(location.country_name), set()).add(code)
            for alias in location.aliases.split(";"):
                if alias:
                    self.aliases[alias] = code
        for name, code in ENGLISH_VARIANTS.items():
            names.setdefault(name_key(name), set()).add(code)
        self.names = {name: next(iter(codes)) for name, codes in names.items() if len(codes) == 1}

    def country_name(self, code: str) -> str:
        """Display name: pycountry `common_name` where present, otherwise `name`."""
        return self.by_code[code].country_name

    def code(self, value: Any) -> tuple[str | None, str]:
        code = clean(value).upper()
        if code in self.by_code:
            return code, "normalized code"
        if code in self.aliases:
            return self.aliases[code], "alias"
        country = pycountry.countries.get(alpha_3=code) if len(code) == 3 else None
        if country:
            return country.alpha_2, "normalized code"
        return None, "unresolved"

    def resolve(self, code: Any, name: Any) -> tuple[str | None, str]:
        normalized, method = self.code(code)
        if normalized is not None:
            return normalized, method
        normalized = self.names.get(name_key(name))
        return (normalized, "country-name fallback") if normalized else (None, "unresolved")

    def feature_code(self, feature: dict) -> str | None:
        properties = feature["properties"]
        # Prefer an actual ISO alpha-2 field to a subdivision-style alias.
        for key in ("ISO_A2", "ISO_A2_EH"):
            code = clean(properties.get(key)).upper()
            if code in self.by_code:
                return code
        for key in ("ISO_A2", "ISO_A2_EH"):
            code, _ = self.code(properties.get(key))
            if code:
                return code
        # A polygon with no ISO code of its own takes the country GADM files its
        # territory under, so it is shaded with the total that already holds its
        # records instead of reading as having none.
        return FEATURE_PARENTS.get(name_key(properties.get("NAME")))
