---
title: Image Similarity Search
name: search_by_image_similarity
parameters:
  reference_species:
    type: string
    required: true
    description: >
      Common or scientific reference name exactly as supplied by the user.
      The database resolves common names; never translate them yourself.
---

Finds species visually similar to a common or scientific reference name using image
embedding distance.

Use ONLY when the user explicitly asks for species that look like, resemble,
or are similar in appearance to a known species.

Examples:

- "butterflies similar to Danaus plexippus" → reference_species="Danaus plexippus"
- "species that look like Morpho menelaus"  → reference_species="Morpho menelaus"

Do NOT call this tool for generic color or location queries.

- "monarch look-alikes" → reference_species="monarch"
- "species resembling the blue morpho" → reference_species="blue morpho"

If the database cannot resolve the name, this tool returns no matches.
