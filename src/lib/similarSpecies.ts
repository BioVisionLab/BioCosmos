export interface SimilarSpeciesList {
  anySides: SimilarSpeciesMeta[];
  dorsal: SimilarSpeciesMeta[];
  ventral: SimilarSpeciesMeta[];
}

export interface SimilarSpeciesMeta {
  imgId: string;
  distance: number;
  species: string;
  source_db: string;
  class_dv: string;
}

async function fetchSimilarSpecies(
  species: string
): Promise<SimilarSpeciesList | null> {
  try {
    const response = await fetch(
      `/api/ml-search/similarity?species=${encodeURIComponent(species)}`
    );
    if (!response.ok) {
      console.error(
        `Failed to fetch similar species for ${species}: ${response.statusText}`
      );
      return null;
    }
    const data = await response.json();
    return data as SimilarSpeciesList;
  } catch (error) {
    console.error(`Error fetching similar species for ${species}:`, error);
    return null;
  }
}

export { fetchSimilarSpecies };
