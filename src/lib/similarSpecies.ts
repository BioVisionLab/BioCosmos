export interface SimilarSpeciesList {
  //   anySides: SimilarSpeciesMeta[];
  dorsal: SimilarSpeciesMeta[];
  ventral: SimilarSpeciesMeta[];
}

/** Which wing surface a panel section is showing. */
export type SimilarSpeciesSide = "dorsal" | "ventral";

export interface SimilarSpeciesMeta {
  imgId: string;
  distance: number;
  /** The name as recorded. */
  species: string;
  /**
   * The species page the card links to: the accepted species' canonical
   * recorded spelling, chosen by the backend. Not `species`, which may be a
   * synonym or misspelling whose own page is orphaned.
   *
   * Optional because a CDN-cached payload from an older backend lacks it.
   */
  speciesKey?: string;
  /**
   * The accepted taxon the record resolves to. Null only when no
   * harmonization run has been loaded, or when the precomputed table predates
   * the accepted-taxon columns — the backend skips unresolved records.
   */
  acceptedName: string | null;
  acceptedRank: string | null;
  updateStatus: string | null;
}

/**
 * The visually-similar panel's data.
 *
 * This lives here rather than inline in the component because the panel is
 * the slowest request the species page makes, and the abort handling below is
 * the only thing keeping a stale response from overwriting a newer one. A
 * second copy of this fetch would be a second copy of that bug.
 *
 * Aborts are rethrown rather than swallowed: the caller has to be able to tell
 * "this request was superseded" from "this species has no neighbours", because
 * only the second one should clear the panel.
 *
 * `side` is required rather than optional. The panel always wants one view at
 * a time -- the two are fetched separately so whichever lands first can paint
 * -- and an optional side would quietly let a caller pay for both.
 */
async function fetchSimilarSpecies(
  species: string,
  side: SimilarSpeciesSide,
  signal?: AbortSignal
): Promise<SimilarSpeciesList | null> {
  try {
    const response = await fetch(
      `/api/ml-search/similarity?species=${encodeURIComponent(
        species
      )}&side=${side}`,
      { signal }
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
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    console.error(`Error fetching similar species for ${species}:`, error);
    return null;
  }
}

export { fetchSimilarSpecies };
