/**
 * Server-side data for the species page.
 *
 * The page used to be a client component that fetched all of this in an
 * effect, so its HTML carried no content and the main image could not start
 * downloading until the bundle had hydrated and two API round-trips had
 * finished. Fetching on the server puts the classification and the first
 * gallery image in the initial HTML.
 */
import { cache } from "react";

import { normalizeColTaxonomy } from "./colTaxonomy";
import { API_HOST } from "./config";
import { LepTraits } from "./leptraits";
import { parseSpeciesSlug, SpeciesData } from "./speciesData";

// A day. The classification, traits and image list change only when the
// backend re-ingests and restarts, which is far rarer than a page view.
const SPECIES_REVALIDATE = 60 * 60 * 24;

// The gallery holds one page of images; the Specimens tab holds the rest.
export const GALLERY_IMAGE_COUNT = 8;

/**
 * The species' classification and traits.
 *
 * Wrapped in `cache()` so the page body and `generateMetadata` share one
 * call. Like `fetchHigherTaxon`, the lifetime sits on the fetch: the page is
 * `force-dynamic`, which only sets a no-store default that an explicit
 * `revalidate` overrides.
 *
 * The backend answers an unresolved name with an empty taxonomy rather than
 * a 404, so a failed request is an outage, not a missing species, and throws
 * to the route's error boundary instead of claiming there is no such species.
 */
export const fetchSpeciesData = cache(
  async (slug: string): Promise<SpeciesData> => {
    if (!API_HOST) throw new Error("API_HOST is not configured");

    const { formattedName } = parseSpeciesSlug(slug);
    const response = await fetch(
      `${API_HOST}/species/${encodeURIComponent(formattedName)}/biology`,
      {
        headers: { Accept: "application/json" },
        next: { revalidate: SPECIES_REVALIDATE, tags: ["species"] },
      },
    );

    if (!response.ok) {
      throw new Error(
        `Failed to load species '${formattedName}': HTTP ${response.status}`,
      );
    }

    const data = await response.json();
    const traits: LepTraits = data?.traits || {};

    return {
      taxonomy: normalizeColTaxonomy(data?.taxonomy ?? data),
      traits,
    };
  },
);

/**
 * The image ids the gallery opens on, dorsal views first.
 *
 * A failure is an empty list rather than an error: the gallery has its own
 * no-image state, and the rest of the page does not depend on it.
 */
export const fetchGalleryImageIds = cache(
  async (slug: string): Promise<string[]> => {
    if (!API_HOST) return [];

    const name = slug.toLowerCase().replace(/ /g, "_");
    const query = `limit=${GALLERY_IMAGE_COUNT}&offset=0&order=view`;

    try {
      const response = await fetch(
        `${API_HOST}/image/${encodeURIComponent(name)}/metadata?${query}`,
        {
          headers: { Accept: "application/json" },
          next: { revalidate: SPECIES_REVALIDATE, tags: ["species"] },
        },
      );

      if (!response.ok) return [];

      const ids = await response.json();

      return Array.isArray(ids) ? ids.slice(0, GALLERY_IMAGE_COUNT) : [];
    } catch {
      return [];
    }
  },
);
