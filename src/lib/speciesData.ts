// import fs from "fs";
import { ColTaxonomy, normalizeColTaxonomy } from "./colTaxonomy";
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

async function getSpeciesData(folderName: string): Promise<SpeciesData | null> {
  const { formattedName } = parseSpeciesSlug(folderName);

  // Fetch taxonomy data from the external service
  try {
    const response = await fetch(
      `/api/taxon-search?species=${encodeURIComponent(formattedName)}`
    );
    if (!response.ok) {
      console.error(
        `Failed to fetch taxonomy data for ${formattedName}: ${response.statusText}`
      );
      return null; // Return null if the request fails
    }
    const dataRaw = await response.json();
    const traits: LepTraits = dataRaw["traits"] || {};
    // Use taxonomy data directly if available, otherwise fallback to the root
    const taxonomy = normalizeColTaxonomy(dataRaw["taxonomy"] ?? dataRaw);
    if (!taxonomy) {
      // Not an error: the classification panel shows its own empty state
      // while the rest of the page carries on.
      console.warn(`No taxonomy data found for ${formattedName}`);
    }
    // Map the response to our SpeciesData format
    return {
      taxonomy,
      traits,
    };
  } catch (error) {
    console.error(`Error fetching taxonomy data for ${formattedName}:`, error);
    return null; // Return null if there was an error
  }
}

export { getSpeciesData, parseSpeciesSlug };
