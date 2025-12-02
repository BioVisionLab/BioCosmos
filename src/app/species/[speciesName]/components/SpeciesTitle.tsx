// Whenever available, we use the combination
// of species name and authorship for the title
// If taxonomy data is not available, we fall back to the species name only

import { TaxonomyData } from "@/lib/speciesData";

// We used the name from the images
function SpeciesTitle({
  taxonomy,
  name,
}: {
  taxonomy: TaxonomyData | null;
  name: string;
}) {
  const titleClass = "text-4xl font-semibold";
  if (taxonomy === null) {
    return (
      <p className={titleClass}>
        <span className="italic">{name}</span>
      </p>
    );
  }

  const authorship = taxonomy.authorship ? taxonomy.authorship.trim() : "";
  const species = taxonomy.species ? taxonomy.species.trim() : "";

  return (
    <p className={titleClass}>
      <span>
        <span className="italic">{species}</span>
        {authorship !== null && authorship !== "" ? " " + authorship : null}
      </span>
    </p>
  );
}

function CommonName({
  vernacularName,
  commonName,
}: {
  vernacularName: string | null;
  commonName: string;
}) {
  const name = vernacularName ?? commonName;

  return <p className="text-2xl text-gray-700 dark:text-gray-300">{name}</p>;
}

function SpeciesHeader({
  taxonomy,
  name,
}: {
  taxonomy: TaxonomyData | null;
  name: string;
}) {
  return (
    <header>
      <div className="mb-6 mt-4 text-center mx-auto">
        <SpeciesTitle taxonomy={taxonomy} name={name} />
        <CommonName
          vernacularName={taxonomy?.vernacularName || null}
          commonName={name}
        />
      </div>
    </header>
  );
}

export default SpeciesHeader;
