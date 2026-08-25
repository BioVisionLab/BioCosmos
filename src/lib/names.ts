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