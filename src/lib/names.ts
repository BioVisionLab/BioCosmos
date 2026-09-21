/**
 * Cleans the species name by replacing underscores with spaces.
 * Make it in sentence case.
 * @param name - The species name to clean.
 * @returns The cleaned species name.
 */
export function cleanSpeciesName(name: string): string {
  const [genus, ...rest] = name.replace(/_/g, " ").split(" ");
  return [genus.charAt(0).toUpperCase() + genus.slice(1), ...rest].join(" ");
}

export function formatSpeciesNameForUrl(name: string): string {
  return name.toLowerCase().replace(/ /g, "_");
}

/**
 * Extracts the binomial name (genus + species) from a full species name
 * that may include subspecies. Returns a URL-safe format.
 * e.g. "danaus_plexippus_plexippus" → "danaus_plexippus"
 */
export function speciesUrlFromName(name: string): string {
  const parts = name.replace(/_/g, " ").trim().split(/\s+/);
  const binomial = parts.length >= 2 ? `${parts[0]}_${parts[1]}` : parts[0];
  return binomial.toLowerCase();
}
/**
 * Strip a parenthesised subgenus from a name.
 *
 * Catalogue of Life writes a zoological species as `Danaus (Danaus)
 * plexippus`. The subgenus has its own row in the classification panel, so
 * carrying it inside every rendered name only makes the name harder to read
 * and harder to line up against the binomial the routes key on.
 */
export function toBinomialName(name: string): string {
  return name
    .replace(/\([^)]*\)/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Whether a recorded name identifies a species rather than just a genus.
 *
 * Records identified only to genus carry a single segment (`vanessa`), and
 * there is no species page for a genus: `/species/vanessa` would render a
 * header over an empty gallery. Anything that cannot pass this should be
 * shown as plain text rather than linked.
 */
export function isSpeciesName(name: string): boolean {
  return (
    toBinomialName(name)
      .split(/[\s_]+/)
      .filter(Boolean).length >= 2
  );
}

/**
 * Whether a recorded name is a trinomial, i.e. names a subspecies.
 *
 * Worth saying out loud next to the accepted binomial, because the record is
 * genuinely more specific than the name above it. A record that differs for
 * any other reason — a misspelling, a synonym — is not: the accepted name
 * already says everything a reader needs.
 */
export function isSubspeciesName(name: string): boolean {
  return (
    toBinomialName(name)
      .split(/[\s_]+/)
      .filter(Boolean).length >= 3
  );
}
