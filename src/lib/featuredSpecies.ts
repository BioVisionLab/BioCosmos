import { API_HOST } from "@/lib/config";

/** One facet of a species page that has something to show. */
export type CompletenessFacet =
  | "images"
  | "views"
  | "distribution"
  | "specimens"
  | "commonName"
  | "traits"
  | "typeMaterial"
  | "similar";

export interface FeaturedSpeciesItem {
  /** Accepted name, from the harmonized taxonomy. */
  species: string;
  /** The recorded slug species pages key on. */
  slug: string;
  family: string | null;
  /** The most confidently dorsal image of the species. */
  imgId: string;
  imageCount: number;
  score: number;
  facets: CompletenessFacet[];
}

export interface FeaturedSpecies {
  /** The UTC day the sample was drawn for. */
  date: string;
  poolSize: number;
  maxScore: number;
  species: FeaturedSpeciesItem[];
}

/** Tray cells in the hero, then cards in the featured rail. */
export const HERO_SPECIMENS = 9;
export const FEATURED_RAIL = 12;

/**
 * A daily random sample of the species with the most complete records, from
 * `/species/featured`.
 *
 * The backend seeds the sample by UTC date, so it is the same all day; the
 * data cache holds it for the same twenty-four hours. The hero tray and the
 * rail share one request (identical fetches in one render are deduplicated),
 * and the rail takes the species after the tray's so no species appears
 * twice on the page.
 *
 * Server-side only: reads API_HOST.
 */
export async function fetchFeaturedSpecies(): Promise<FeaturedSpecies | null> {
  try {
    const response = await fetch(
      `${API_HOST}/species/featured?limit=${HERO_SPECIMENS + FEATURED_RAIL}`,
      { next: { revalidate: 60 * 60 * 24 } },
    );
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}
