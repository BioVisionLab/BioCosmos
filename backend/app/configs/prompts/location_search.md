---
title: Location-Based Species Search
name: search_by_location
parameters:
  location:
    type: string
    required: true
    description: >
      ISO 3166-1 alpha-2 country code (e.g. "BR", "ID", "CR").
      Always convert country names to their 2-letter code.
      For multi-country regions use the most representative country code.
  limit:
    type: integer
    required: false
    default: 500
    description: Maximum number of species to return.
---

Finds species with known occurrences in a specific country or region,
sourced from GBIF occurrence records.

Use when the user mentions any country, territory, or geographic region.

Examples:

- "butterflies in Brazil"      → location="BR"
- "species from Indonesia"     → location="ID"
- "Amazon rainforest species"  → location="BR"
- "Southeast Asia butterflies" → location="ID"
