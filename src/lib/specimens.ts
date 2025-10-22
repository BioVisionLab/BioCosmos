export interface SpecimenData {
  species: string;
  imageCounts: number;
}

async function fetchSpecimenData(
  speciesName: string
): Promise<SpecimenData | null> {
  const speciesNameEncoded = speciesName.replace(" ", "_");
  const response = await fetch(
    `api/specimen-search?species=${encodeURIComponent(speciesNameEncoded)}`
  );

  if (!response.ok) {
    throw new Error(
      `Failed to fetch specimen stats. Status: ${response.status}`
    );
  }

  const specimenData: SpecimenData = await response.json();
  return specimenData;
}

export { fetchSpecimenData };
