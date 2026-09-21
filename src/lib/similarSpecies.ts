export interface SimilarSpeciesList {
  //   anySides: SimilarSpeciesMeta[];
  dorsal: SimilarSpeciesMeta[];
  ventral: SimilarSpeciesMeta[];
}

export interface SimilarSpeciesMeta {
  imgId: string;
  distance: number;
  /**
   * The name as recorded, and the link target.
   *
   * Every image endpoint keys on `image_meta.species`, so a link built from
   * the accepted name would open a species page with an empty gallery for
   * exactly the renamed taxa this panel surfaces.
   */
  species: string;
  /**
   * The accepted taxon the record resolves to. Null only when no
   * harmonization run has been loaded, or when the precomputed table predates
   * the accepted-taxon columns — the backend skips unresolved records.
   */
  acceptedName: string | null;
  acceptedRank: string | null;
  updateStatus: string | null;
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
