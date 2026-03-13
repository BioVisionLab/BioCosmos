---
title: Color and Pattern Search
name: search_by_color
parameters:
  color_description:
    type: string
    required: true
    description: >
      Natural language color or pattern description.
      Can be simple ("blue") or complex ("orange and black stripes").
  limit:
    type: integer
    required: false
    default: 150
    description: Target number of species to return.
---

Finds species matching a color or visual pattern description using
CLIP-based image embedding search.

Use when the user describes colors, patterns, or visual appearance.

Examples:

- "blue wings"                    → color_description="blue wings"
- "orange spots"                  → color_description="orange spots"
- "iridescent green"              → color_description="iridescent green"
- "black and white striped wings" → color_description="black and white striped wings"

Do NOT call this for location or habitat queries.
