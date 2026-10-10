# Analysis data

Reference data and screenshots used by the publication notebooks. This file
records their sources and how they are used; generated figures and summaries go
to `analyses/results/`.

## Country markers

[`country_locations.csv`](../../packages/harmonize-core/src/harmonize_core/data/country_locations.csv)
is bundled with `harmonize-core` and shared by the notebooks, the
`/stats/country` API, and the site's map. It provides one label location for
each of the 249 ISO 3166-1 countries and territories, plus Kosovo (`XK`). A
marker is used only when a country or territory has no polygon in the 110m
basemap. The notebooks read local data and do not download it.

### Sources

The marker coordinates come from Natural Earth v5.1.2, in the public domain:

- [10m admin-0 countries](https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_countries.geojson)
- [10m admin-0 map units](https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_map_units.geojson)

### Table construction

- Coordinates use `LABEL_X` (longitude) and `LABEL_Y` (latitude). Each row
  records its source URL and feature name.
- Match features where `ISO_A2` or `ISO_A2_EH` equals the code, preferring exact
  `ISO_A2`, then the countries dataset over map units, then source order.
- Names come from pycountry 24.6.1, using `common_name` when available and
  `name` otherwise. `aliases` lists subdivision-form codes, separated by
  semicolons.
- Normalization also accepts `UK` → `GB`, `EL` → `GR`, ISO alpha-3 codes, and
  the names in `packages/harmonize-core/src/harmonize_core/countries.py`.

Marker coordinates identify reporting units rather than specimen locations. For
example, the United States Minor Outlying Islands (`UM`) marker is at Wake
Atoll.

## Mimicry pairs

[`mimicry_pairs.csv`](mimicry_pairs.csv) lists published butterfly mimicry pairs
(Müllerian, Batesian, or context-dependent), one per row, with notes, key
publications, and DOIs. `Availability` records whether both species have dorsal
images in the collection. [`mimicry.ipynb`](../notebooks/mimicry.ipynb) tests
only pairs with images for both species. Cite the publications listed in the CSV
when using these pairs.

## Other files

- `ne_110m_admin_0_countries.geojson`: Natural Earth 110m basemap for the
  country map.
- `indexing_benchmark.csv`: legacy index benchmark; the current notebooks do not
  read it.
- `screenshots/`: app screenshots for `screenshot_bento.ipynb`.
