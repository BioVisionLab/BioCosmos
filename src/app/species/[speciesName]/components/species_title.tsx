// Whenever available, we use the combination
// of species name and authorship for the title
// If taxonomy data is not available, we fall back to the species name only

import { TaxonomyData } from "@/lib/speciesData";

// We used the name from the images
export function SpeciesTitle({
  taxonomy,
  name,
}: {
  taxonomy: TaxonomyData | null;
  name: string;
}) {
  if (taxonomy === null) {
    return <span className="italic">{name}</span>;
  }

  const authorship = taxonomy.authorship ? taxonomy.authorship.trim() : "";
  const species = taxonomy.species ? taxonomy.species.trim() : "";

  return (
    <span>
      <span className="italic">{species}</span>
      {authorship !== null && authorship !== "" ? " " + authorship : null}
    </span>
  );
}
