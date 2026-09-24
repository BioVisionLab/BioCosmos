---
title: Ecological Trait Search
name: search_by_traits
parameters:
  canopy:
    type: string
    required: false
    enum: [closed, open, mixed, generalist, edge]
    description: Canopy cover the species lives under.
  edge:
    type: string
    required: false
    enum: [associated, avoidant]
    description: Association with habitat edges.
  moisture:
    type: string
    required: false
    enum: [wet, dry]
    description: Mesic (wet, humid) or xeric (dry, arid) habitat.
  disturbance:
    type: string
    required: false
    enum: [tolerant, avoidant]
    description: Tolerance of disturbed habitat.
  voltinism:
    type: string
    required: false
    enum: [univoltine, bivoltine, multivoltine]
    description: Generations per year.
  diapause_stage:
    type: string
    required: false
    enum: [egg, larva, pupa, adult]
    description: Life stage that overwinters or diapauses.
  oviposition:
    type: string
    required: false
    enum: [single, clustered]
    description: Eggs laid singly or in clusters.
  hostplant_family:
    type: string
    required: false
    description: Larval host plant family, a botanical family name.
  host_breadth:
    type: string
    required: false
    enum: [specialist, generalist]
    description: One host plant family, or three or more.
  flight_months:
    type: array
    required: false
    items: [jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, dec]
    description: Months adults fly; a species flying in any of them matches.
  wing_size:
    type: string
    required: false
    enum: [small, medium, large]
    description: Wingspan relative to the other species in the collection.
---

Finds species by ecology and life history, using the LepTraits database.

Use when the user names a habitat, life-history, host-plant, flight-season
or body-size characteristic. Pass at least one argument, and only the ones
the user asked for.

`hostplant_family` is a plant family ending in -aceae. Translate common
plant names: legumes → Fabaceae, grasses → Poaceae, milkweeds → Apocynaceae,
passion vines → Passifloraceae, citrus → Rutaceae, oaks → Fagaceae.
For seasons, list the months: summer → jun, jul, aug (northern hemisphere).

Examples:

- "canopy species"                   → canopy="closed"
- "open-country butterflies"         → canopy="open"
- "disturbance-tolerant butterflies" → disturbance="tolerant"
- "dry habitat, forest edge species" → moisture="dry", edge="associated"
- "rainforest interior species"      → canopy="closed", moisture="wet", edge="avoidant"
- "univoltine butterflies"           → voltinism="univoltine"
- "overwinter as pupae"              → diapause_stage="pupa"
- "caterpillars feed on legumes"     → hostplant_family="Fabaceae"
- "host-plant specialists"           → host_breadth="specialist"
- "flies in June"                    → flight_months=["jun"]
- "large butterflies"                → wing_size="large"
