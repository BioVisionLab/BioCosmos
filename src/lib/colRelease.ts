/**
 * The Catalogue of Life release the backend ingested.
 *
 * Server-only: `API_HOST` is not a `NEXT_PUBLIC_` variable. The root layout
 * calls this once and hands the label to every attribution through
 * `ColReleaseProvider`.
 */
import { API_HOST } from "@/lib/config";
import { type ColRelease, formatColRelease } from "@/lib/colTaxonomy";

/** A release changes once a month at most; an hour is plenty fresh. */
const RELEASE_REVALIDATE_SECONDS = 3600;

/**
 * Fetch the ingested release's label, or null when it cannot be had.
 *
 * Null covers the Docker build, where `API_HOST` is unset, a backend that is
 * down, and one with no release recorded; attributions then fall back to
 * `COL_RELEASE`.
 */
export async function fetchColReleaseLabel(): Promise<string | null> {
  if (!API_HOST) return null;

  try {
    const response = await fetch(`${API_HOST}/taxonomy/release`, {
      headers: { Accept: "application/json" },
      next: { revalidate: RELEASE_REVALIDATE_SECONDS },
    });

    if (!response.ok) return null;

    const release = (await response.json()) as ColRelease;

    return release?.version ? formatColRelease(release) : null;
  } catch (error) {
    console.error("Failed to fetch the Catalogue of Life release:", error);

    return null;
  }
}
