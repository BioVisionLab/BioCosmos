---
title: Image Similarity Search
name: search_by_image_similarity
parameters:
  reference_species:
    type: string
    required: true
    description: >
      Scientific name of the reference species (e.g. "Danaus plexippus").
      Convert common names to scientific names if possible.
  limit:
    type: integer
    required: false
    default: 50
    description: Maximum number of similar images to retrieve.
---

Finds species visually similar to a specific scientific name using image
embedding distance.

Use ONLY when the user explicitly asks for species that look like, resemble,
or are similar in appearance to a known species.

Examples:

- "butterflies similar to Danaus plexippus" → reference_species="Danaus plexippus"
- "species that look like Morpho menelaus"  → reference_species="Morpho menelaus"

Do NOT call this tool for generic color or location queries.
