/**
 * URLs for taxon pages.
 *
 * Catalogue of Life capitalizes its names and the species route has always
 * been lowercase, so a canonical form has to be chosen somewhere. It is
 * chosen here: lowercase, spaces as underscores, for every rank. One casing
 * also means one cache key — serving a family at both `/family/Nymphalidae`
 * and `/family/nymphalidae` would split a thirty-day cache in two and leave
 * the page competing with itself in search results.
 *
 * A slug is only ever a lookup key. Nothing un-slugs one for display: the
 * name shown on a page comes from the payload, because title-casing a slug
 * back is lossy and would eventually mangle a hyphenated or accented name.
 */

import { formatSpeciesNameForUrl, speciesUrlFromName } from "@/lib/names";

export function toTaxonSlug(name: string): string {
  return formatSpeciesNameForUrl(name.trim());
}

/** Whether a route parameter is already canonical, i.e. needs no redirect. */
export function isCanonicalTaxonSlug(slug: string): boolean {
  return slug === toTaxonSlug(slug);
}

/**
 * The one order the site has a page for. The collection is Lepidoptera, so
 * `/order` needs no parameter; a second order would give it one.
 */
export const ORDER_NAME = "Lepidoptera";
export const ORDER_PATH = "/order";

/** The order page, or null for any order other than the one it serves. */
export function orderHref(name: string): string | null {
  return toTaxonSlug(name) === toTaxonSlug(ORDER_NAME) ? ORDER_PATH : null;
}

export function familyHref(name: string): string {
  return `/family/${encodeURIComponent(toTaxonSlug(name))}`;
}

export function genusHref(name: string): string {
  return `/genus/${encodeURIComponent(toTaxonSlug(name))}`;
}

/**
 * The link to a species page the backend chose, or null when it chose none.
 *
 * Search and similarity results carry a `speciesKey`: the accepted species'
 * canonical recorded spelling, resolved server-side so the link never lands
 * on a page orphaned under a synonym or misspelling. It is used verbatim —
 * unlike `speciesHref`, never trimmed — because the backend already picked a
 * binomial, and null means the record has no species page to open.
 */
export function speciesPageHref(speciesKey?: string | null): string | null {
  const key = speciesKey?.trim();
  return key ? `/species/${encodeURIComponent(toTaxonSlug(key))}` : null;
}

/**
 * The species page resolves its images on the name the collection recorded,
 * so a link built from an accepted name that differs would reach a page with
 * nothing on it. Callers pass the recorded key; `speciesUrlFromName` trims a
 * recorded trinomial to the binomial the route expects.
 */
export function speciesHref(recordedName: string): string {
  return `/species/${encodeURIComponent(speciesUrlFromName(recordedName))}`;
}
