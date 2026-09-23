# Country marker reference

`country_locations.csv` provides one label location for each of the 249 ISO 3166-1
countries/territories and Kosovo (`XK`). It is used only when a reporting unit lacks
a separate polygon in the supplied 110m basemap. All marker locations are checked in;
notebook execution does not download data.

Sources: Natural Earth **v5.1.2**, public-domain data:

- [10m admin-0 countries](https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_countries.geojson)
- [10m admin-0 map units](https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_map_units.geojson)

The table uses `LABEL_X` and `LABEL_Y` as longitude and latitude in degrees. Each row
retains its exact source URL and feature name. To reproduce the selection, find features
where either `ISO_A2` or `ISO_A2_EH` equals the target code, prefer exact `ISO_A2`
matches, then prefer the countries dataset over map units, retaining source order for
ties. ISO names come from pycountry 24.6.1 (`common_name` where present, otherwise
`name`); Kosovo is the explicit supplement. `aliases` records subdivision-form codes
from the matching features, separated by semicolons. Runtime normalization additionally
accepts `UK` → `GB`, `EL` → `GR`, ISO alpha-3 codes, and the exact unique names defined
in `analyses/helpers/country_mapping.py`.

The United States Minor Outlying Islands (`UM`) use the country dataset's representative
label at Wake Atoll. This identifies the reporting unit, not the island on which any
specimen was collected. The same distinction applies to all multi-island units.

The notebook's audit table preserves original identifiers, normalization methods,
representation, source, and counts. Countries without explicit attributable information
remain unresolved; no coordinate or parent-country inference is performed.
