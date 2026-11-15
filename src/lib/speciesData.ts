import { ColTaxonomy } from "./colTaxonomy";
import { LepTraits } from "./leptraits";

/**
 * A species classification, as returned by the biology endpoint.
 *
 * This is the Catalogue of Life shape. It has no `redlistCategory`: CoL
 * publishes no conservation status, and the IUCN badge it fed was removed
 * along with the live GBIF lookup.
 */
export type TaxonomyData = ColTaxonomy;

export interface SpeciesData {
  /**
   * Null when the name could not be resolved against Catalogue of Life. The
   * rest of the page — gallery, traits, specimens, literature — does not come
   * from CoL, so an unresolved name still renders.
   */
  taxonomy: TaxonomyData | null;
  traits: LepTraits;
}

/**
 * Derive the genus and species from a route slug such as
 * `zeuxidia_amethystus`. Useful for painting the page header before the
 * taxonomy request resolves.
 */
function parseSpeciesSlug(folderName: string): {
  genus: string;
  species: string;
  formattedName: string;
} {
  let genus = "Unknown";
  let species = "sp.";
  const parts = folderName.split("_");

  if (parts.length === 2) {
    genus = parts[0].charAt(0).toUpperCase() + parts[0].slice(1).toLowerCase();
    species = parts[1].toLowerCase();
  }

  return { genus, species, formattedName: `${genus} ${species}` };
}

export { parseSpeciesSlug };
