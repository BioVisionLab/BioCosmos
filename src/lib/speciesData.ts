// import fs from "fs";
import { LepTraits } from "./leptraits";

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

export interface SpeciesImageUmap {
  imgId: string;
  umapX: number;
  umapY: number;
  clusterLabel?: number;
}

export interface ClassificationSearchResult {
  matchCategory: string;
  classification: TaxonomyData;
}

async function getSpeciesData(folderName: string): Promise<SpeciesData | null> {
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

async function fetchTaxonClassification(
  species: string
): Promise<ClassificationSearchResult[] | null> {
  try {
    const response = await fetch(
      `/api/db-search?q=${encodeURIComponent(species)}`
    );
    if (!response.ok) {
      console.error(
        `Failed to fetch classification for ${species}: ${response.statusText}`
      );
      return null;
    }
    const data = await response.json();
    return data["results"] || null;
  } catch (error) {
    console.error(`Error fetching classification for ${species}:`, error);
    return null;
  }
}

async function fetchSpeciesImageUmap(
  species: string
): Promise<SpeciesImageUmap[] | null> {
  try {
    const response = await fetch(
      `/api/stats/umap?species=${encodeURIComponent(species)}`
    );
    if (!response.ok) {
      console.error(
        `Failed to fetch UMAP data for ${species}: ${response.statusText}`
      );
      return null;
    }
    const data = await response.json();
    return data["umapEmbeddings"] || null;
  } catch (error) {
    console.error(`Error fetching UMAP data for ${species}:`, error);
    return null;
  }
}

export { getSpeciesData, fetchTaxonClassification, fetchSpeciesImageUmap };
