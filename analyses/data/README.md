# Analysis data

## Country markers

[`country_locations.csv`](../../packages/harmonize-core/src/harmonize_core/data/country_locations.csv)
ships with `harmonize-core`, so the notebooks, the `/stats/country` API, and the site's map
share it. It gives one label location for each of the 249 ISO 3166-1 countries and
territories plus Kosovo (`XK`), used only when a unit has no polygon in the 110m basemap.
Notebooks never download data.

### Sources

Natural Earth **v5.1.2**, public domain:

- [10m admin-0 countries](https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_countries.geojson)
- [10m admin-0 map units](https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_map_units.geojson)

### Reproducing the table

- Coordinates are `LABEL_X` (longitude) and `LABEL_Y` (latitude); each row keeps its source
  URL and feature name.
- Match features where `ISO_A2` or `ISO_A2_EH` equals the code, preferring exact `ISO_A2`,
  then the countries dataset over map units, then source order.
- Names come from pycountry 24.6.1 (`common_name`, else `name`). `aliases` lists
  subdivision-form codes, separated by semicolons.
- Normalization also accepts `UK` → `GB`, `EL` → `GR`, ISO alpha-3 codes, and the names in
  `packages/harmonize-core/src/harmonize_core/countries.py`.

A marker identifies a reporting unit, not a collection site: the United States Minor
Outlying Islands (`UM`) sit at Wake Atoll, for example.

## Mimicry pairs

[`mimicry_pairs.csv`](mimicry_pairs.csv) lists published butterfly mimicry pairs (Müllerian,
Batesian, or context-dependent), one per row, with notes, key publications, and DOIs.
`Availability` records whether both species have dorsal images in the collection; only
available pairs are tested by `notebooks/mimicry.ipynb`. Cite the listed publications, not
this table.

## Other files

- `ne_110m_admin_0_countries.geojson`: Natural Earth 110m basemap for the country map.
- `indexing_benchmark.csv`: legacy index benchmark, no longer read.
- `screenshots/`: app screenshots for `screenshot_bento.ipynb`.
