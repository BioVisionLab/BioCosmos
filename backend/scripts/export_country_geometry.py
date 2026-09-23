"""Write the country geometry the site's species-by-country map shades.

    cd backend && uv run python scripts/export_country_geometry.py

Reads the Natural Earth 110m basemap the data summary notebook draws and
writes `public/geo/countries-110m.json`, keyed by the ISO alpha-2 code that
`harmonize_core.countries.CountryLookup.feature_code` assigns. That is the same
lookup `/stats/country` normalizes GADM codes with, so a polygon and its
count always meet on one code. Names are deliberately left out: the page takes
them from the API, so there is one name table rather than two.

Countries with no polygon of their own at this scale (Singapore, Andorra, ...)
get a point at their Natural Earth label location, drawn as a marker, exactly
as the notebook does.

Coordinates are rounded to two decimals (about 1 km), well under the 110m
basemap's own resolution, which is most of the size saving.
"""

import json
from pathlib import Path

from harmonize_core.countries import CountryLookup

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "analyses/data/ne_110m_admin_0_countries.geojson"
TARGET = ROOT / "public/geo/countries-110m.json"
PRECISION = 2


def _round(coordinates):
    if isinstance(coordinates[0], (int, float)):
        return [round(value, PRECISION) for value in coordinates]
    return [_round(part) for part in coordinates]


def _dedupe_ring(ring: list) -> list:
    """Drop consecutive vertices that rounding collapsed onto each other."""
    kept = [ring[0]]
    for point in ring[1:]:
        if point != kept[-1]:
            kept.append(point)
    return kept


def _clean_geometry(geometry: dict) -> dict:
    rounded = _round(geometry["coordinates"])
    if geometry["type"] == "Polygon":
        rounded = [_dedupe_ring(ring) for ring in rounded]
    else:
        rounded = [[_dedupe_ring(ring) for ring in polygon] for polygon in rounded]
    return {"type": geometry["type"], "coordinates": rounded}


def _polygons(geometry: dict) -> list:
    cleaned = _clean_geometry(geometry)
    return (
        [cleaned["coordinates"]]
        if cleaned["type"] == "Polygon"
        else cleaned["coordinates"]
    )


def main() -> None:
    lookup = CountryLookup()
    features = json.loads(SOURCE.read_text())["features"]
    # One feature per code: Somaliland's polygon joins Somalia's, so the map's
    # feature ids (the code) stay unique and hover highlights both together.
    polygons: dict[str, list] = {}
    for feature in features:
        code = lookup.feature_code(feature)
        if code is None or feature["geometry"] is None:
            continue
        polygons.setdefault(code, []).extend(_polygons(feature["geometry"]))
    output = [
        {
            "type": "Feature",
            "properties": {"code": code},
            "geometry": {"type": "MultiPolygon", "coordinates": parts}
            if len(parts) > 1
            else {"type": "Polygon", "coordinates": parts[0]},
        }
        for code, parts in sorted(polygons.items())
    ]
    polygon_codes = set(polygons)
    for code, location in sorted(lookup.by_code.items()):
        if code in polygon_codes:
            continue
        output.append(
            {
                "type": "Feature",
                "properties": {"code": code, "marker": True},
                "geometry": {
                    "type": "Point",
                    "coordinates": _round([location.longitude, location.latitude]),
                },
            }
        )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": output}, separators=(",", ":")
        )
    )
    print(
        f"Wrote {TARGET.relative_to(ROOT)}: {len(polygon_codes)} country polygons, "
        f"{len(output) - len(polygon_codes)} markers, {TARGET.stat().st_size / 1024:.0f} KB"
    )


if __name__ == "__main__":
    main()
