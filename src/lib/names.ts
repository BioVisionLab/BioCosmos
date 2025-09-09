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
