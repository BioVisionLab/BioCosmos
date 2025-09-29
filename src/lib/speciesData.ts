// import fs from "fs";
import { API_HOST } from "./config";
import { cleanSpeciesName } from "./names";

const TAXONOMY_SERVICE_URL = `${API_HOST}/taxon`;

export interface TaxonomyData {
  kingdom: string;
  phylum: string;
  class: string;
  order: string;
  family: string;
  genus: string;
  species: string;
  authorship: string;
  vernacularName: string;
  redlistCategory: string;
  taxonomicStatus: string;
}

export interface SimilarSpeciesMeta {
  imgId: string;
  species: string;
  distance: number;
}

export interface SpeciesData {
  taxonomy: TaxonomyData;
  traits: LepTraits;
  similarSpecies: SimilarSpeciesMeta[];
}

export interface LepTraits {
  wingspan_lower_female?: number;
  wingspan_upper_female?: number;
  wingspan_lower_male?: number;
  wingspan_upper_male?: number;
  wingspan_lower_unspecified?: number;
  wingspan_upper_unspecified?: number;
  forewing_lower_female?: number;
  forewing_upper_female?: number;
  forewing_lower_male?: number;
  forewing_upper_male?: number;
  forewing_lower_unspecified?: number;
  forewing_upper_unspecified?: number;
  jan_adult_presence?: string;
  feb_adult_presence?: string;
  mar_adult_presence?: string;
  apr_adult_presence?: string;
  may_adult_presence?: string;
  jun_adult_presence?: string;
  jul_adult_presence?: string;
  aug_adult_presence?: string;
  sep_adult_presence?: string;
  oct_adult_presence?: string;
  nov_adult_presence?: string;
  dec_adult_presence?: string;
  flight_duration?: number;
  diapause_stage?: string;
  voltinism?: string;
  oviposition_style?: string;
  canopy_affinity?: string;
  edge_affinity?: string;
  moisture_affinity?: string;
  disturbance_affinity?: string;
  number_of_hostplant_families?: number;
  sole_hostplant_family?: string;
  primary_hostplant_family?: string;
  secondary_hostplant_family?: string;
  equal_hostplant_family?: string;
  number_of_hostplant_accounts?: number;
  date_created?: string;
}

export async function getSpeciesData(
  folderName: string
): Promise<SpeciesData | null> {
  // We will capture the species name from the folder name by splitting on underscores
  let genus = "Unknown";
  let species = "sp.";
  const parts = folderName.split("_");
  if (parts.length === 2) {
    genus = parts[0].charAt(0).toUpperCase() + parts[0].slice(1).toLowerCase();
    species = parts[1].toLowerCase();
  }
  const formattedName = `${genus} ${species}`;

  // Fetch taxonomy data from the external service
  try {
    const response = await fetch(
      `${TAXONOMY_SERVICE_URL}?q=${encodeURIComponent(formattedName)}`
    );
    if (!response.ok) {
      console.error(
        `Failed to fetch taxonomy data for ${formattedName}: ${response.statusText}`
      );
      return null; // Return null if the request fails
    }
    const dataRaw = await response.json();
    const traits: LepTraits = dataRaw["traits"] || {};
    const similarSpecies: SimilarSpeciesMeta[] =
      dataRaw["similarSpecies"] || [];
    const cleanedSimilarSpecies = similarSpecies.map((item) => ({
      imgId: item.imgId,
      species: item.species,
      distance: parseFloat(item.distance.toFixed(4)), // Round distance to 4 decimal places
    }));
    // Use taxonomy data directly if available, otherwise fallback to the root
    const taxonomy = dataRaw["taxonomy"] || dataRaw; // Handle different response structures
    console.log(`Fetched taxonomy data for ${formattedName}:`, taxonomy);
    if (!taxonomy) {
      console.warn(`No taxonomy data found for ${formattedName}`);
      return null; // Return null if no data is found
    }
    // Map the response to our SpeciesData format
    return {
      taxonomy,
      traits,
      similarSpecies: cleanedSimilarSpecies,
    };
  } catch (error) {
    console.error(`Error fetching taxonomy data for ${formattedName}:`, error);
    return null; // Return null if there was an error
  }
}
