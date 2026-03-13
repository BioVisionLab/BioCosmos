---
title: Ecological Trait Search
name: search_by_traits
parameters:
  canopy_affinity:
    type: string
    required: false
    enum: [High, Medium, Low]
    description: Preference for canopy cover.
  edge_affinity:
    type: string
    required: false
    enum: [High, Medium, Low]
    description: Preference for habitat edges.
  moisture_affinity:
    type: string
    required: false
    enum: [High, Medium, Low]
    description: Preference for moisture.
  disturbance_affinity:
    type: string
    required: false
    enum: [High, Medium, Low]
    description: Tolerance of habitat disturbance.
  limit:
    type: integer
    required: false
    default: 100
    description: Maximum number of species to return.
---

Finds species by ecological traits and habitat preferences using
structured trait data from the LepTraits database.

Use when the user specifies any habitat characteristic.
At least one trait argument must be provided.

Examples:

- "canopy species"                    → canopy_affinity="High"
- "disturbance-tolerant butterflies"  → disturbance_affinity="High"
- "dry habitat, forest edge species"  → moisture_affinity="Low", edge_affinity="High"
