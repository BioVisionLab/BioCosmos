---
title: Location-Based Species Search
name: search_by_location
parameters:
  country:
    type: string
    required: true
    description: >
      ISO 3166-1 alpha-2 country code (e.g. "BR", "ID", "CR").
      Always convert country names to their 2-letter code.
      For multi-country regions use the most representative country code.
  state_province:
    type: string
    required: false
    description: >
      First-level administrative region (state, province, department) inside
      that country, as the user named it (e.g. "Sabah", "Minas Gerais").
      Omit unless the user names one.
---

Finds species with known occurrences in a country, optionally narrowed to
one of its states or provinces. Places come from GADM-validated specimen
coordinates, falling back to the recorded locality.

Use when the user mentions any country, territory, state, province, or
geographic region.

Only pass `state_province` for a first-level region the user actually named.
Never pass a city, county, park, river, mountain, or ecoregion as
`state_province`; use the country alone instead.

Examples:

- "butterflies in Brazil"          → country="BR"
- "species from Indonesia"         → country="ID"
- "butterflies of Sabah"           → country="MY", state_province="Sabah"
- "Minas Gerais butterflies"       → country="BR", state_province="Minas Gerais"
- "butterflies in Georgia, USA"    → country="US", state_province="Georgia"
- "Amazon rainforest species"      → country="BR"
- "Southeast Asia butterflies"     → country="ID"
