# Analysis Reference Data

Static reference files and screenshots used by the notebooks in `analyses/notebooks/`.

## `mimicry_pairs.csv`

Curated list of 12 published butterfly mimicry pairs evaluated in `notebooks/mimicry.ipynb` and `notebooks/search_performance.ipynb` (`analyses/helpers/mimicry.py`).

| Column | Description |
| :--- | :--- |
| `pair_id` | Short identifier for the pair (`MP01`–`MP12`) |
| `ring` | Mimicry ring or complex name (e.g., *Postman*, *Tiger*, *Pipevine*) |
| `model_species`, `mimic_species` | Lowercase `genus_species` slugs matching `image_meta.species` (resolved to accepted Catalogue of Life names via `image_meta_taxonomy`) |
| `relationship` | `Müllerian` (co-mimics sharing warning signals) or `Batesian` (palatable mimic resembling an unpalatable model) |
| `shared_location` | Geographic region where the two species co-occur |
| `source_citation`, `source_doi` | Primary literature source and DOI |
| `notes` | Brief context on the mimicry system |

### Literature sources

- Brower, L. P. (1958). Bird predation and foodplant specificity in closely related procryptic insects. *Evolution*, 12(1), 32–47. https://doi.org/10.1111/j.1558-5646.1958.tb02926.x
- Clarke, C. A., & Sheppard, P. M. (1960). The evolution of mimicry in the butterfly *Papilio dardanus*. *Heredity*, 14, 163–173. https://doi.org/10.1038/hdy.1960.14
- Flanagan, N. S., Tobler, A., Davison, A., Pybus, O. G., Kapan, D. D., Planas, S., Linares, M., Heckel, D., & McMillan, W. O. (2004). Historical demographic inference using single nucleotide polymorphisms: a comparison of methods in *Heliconius* butterflies. *Molecular Ecology*, 13(4), 901–913. https://doi.org/10.1111/j.1365-294X.2004.02102.x
- Joron, M., Wynne, I. R., Lamas, G., & Mallet, J. (1999). Variable selection and the coexistence of multiple, sympatric tiger mimicry rings in the butterfly *Heliconius numata*. *Evolutionary Ecology*, 13, 721–754. https://doi.org/10.1023/A:1010875213123
- Kunte, K. (2009). Female-limited mimetic polymorphism: a review of theories and a critique of sexual selection as an evolutionary driver. *Evolution*, 63(11), 2791–2806. https://doi.org/10.1111/j.1558-5646.2009.00797.x
- Kunte, K., Zhang, W., Tenger-Trolander, A., Palmer, D. H., Martin, A., Reed, R. D., Mullen, S. P., & Kronforst, M. R. (2014). *doublesex* is a mimicry supergene. *Nature*, 507(7491), 229–232. https://doi.org/10.1038/nature13112
- Mullen, S. P. (2006). Wing pattern evolution and the origin of mimicry among North American admiral butterflies (*Limenitis*: Nymphalidae). *Evolution*, 60(6), 1207–1218. https://doi.org/10.1111/j.0014-3820.2006.tb01199.x
- Pinheiro, C. E. G., & Freitas, A. V. L. (2014). Some possible cases of escape mimicry in Neotropical butterflies. *Neotropical Entomology*, 43(5), 393–398. https://doi.org/10.1007/s13744-014-0240-y
- Prudic, K. L., Jeon, J., & Papaj, D. R. (2019). Batesian mimicry and the evolution of wing pattern diversity in *Adelpha* butterflies. *Frontiers in Ecology and Evolution*, 7, 290. https://doi.org/10.3389/fevo.2019.00290
- Ritland, D. B., & Brower, L. P. (1991). The viceroy butterfly is not a Batesian mimic. *Nature*, 350(6318), 497–498. https://doi.org/10.1038/350497a0
- Symula, R., Keogh, J. S., & Cannatella, D. C. (2001). Müllerian mimicry in Amazonian poison frogs: a molecular phylogenetic test of the mimicry hypothesis. *Proceedings of the Royal Society B*, 268(1484), 2415–2421. https://doi.org/10.1098/rspb.2001.1812

## `ne_110m_admin_0_countries.geojson`

Public-domain 1:110m admin-0 country boundaries from [Natural Earth](https://github.com/nvkelso/natural-earth-vector) (`geojson/ne_110m_admin_0_countries.geojson`), used by `notebooks/data_summary.ipynb` (`analyses/helpers/country_mapping.py`) to plot country-level species richness.

How countries are matched and drawn:

- **ISO code resolution**: `country_mapping.py` normalizes recorded country names (`normalized_country`, or `gadm_ADM_0` when `validation_status = 'IMPUTED_COUNTRY'`) to ISO 3166-1 alpha-3 codes through `harmonize-core` (`packages/harmonize-core/src/harmonize_core/countries.py`) and matches them to Natural Earth's `ADM0_A3` property.
- **Merged and non-standard polygons**: Split or disputed Natural Earth features are mapped so their records count toward the corresponding polygon (`-99` Somaliland → `SOM`; `CYN` Northern Cyprus and `CNM` Cyprus No Mans Area → `CYP`; `PSX` ↔ `PSE`; `KOS` ↔ `XKX`; `SDS` ↔ `SSD`; `SAH` ↔ `ESH`; `TWN` for Taiwan).
- **Point markers for small territories**: Because the 1:110m basemap omits small island nations and overseas territories (such as Réunion, French Guiana, Mauritius, Comoros, São Tomé and Príncipe, and Singapore), `country_mapping.py` draws them as fixed-size circular markers at representative coordinates from `NATURAL_EARTH_110M_MARKERS`.

## `screenshots/`

Raw PNG screenshots of the BioCosmos web application. `notebooks/screenshot_bento.ipynb` selects four screenshots, frames them in a 2 × 2 grid with rounded glass borders and drop shadows, and exports:

- `analyses/results/screenshot_bento.png` — Labeled `a`–`d` for manuscript figures.
- `docs/images/screenshot_bento.png` — Unlabeled copy displayed in the root `README.md`.
