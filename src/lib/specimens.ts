export interface SpecimenData {
  species: string;
  imageCounts: number;
}

async function fetchSpecimenData(
  speciesName: string
): Promise<SpecimenData | null> {
  // Normalize species name to match the external API's expected format:
  // trim, lowercase, and replace all whitespace with underscores.
  const speciesNameEncoded = speciesName.trim().toLowerCase().replace(/\s+/g, "_");
  const response = await fetch(
    `/api/specimens?species=${encodeURIComponent(speciesNameEncoded)}`
  );

  if (!response.ok) {
    throw new Error(
      `Failed to fetch specimen stats. Status: ${response.status}`
    );
  }

  const raw = await response.json();

  // Normalize a variety of possible external API response shapes into
  // our internal SpecimenData shape. External APIs may return an array
  // of specimen objects, or an object with different count field names.
  let imageCounts = 0;
  if (Array.isArray(raw)) {
    imageCounts = raw.length;
  } else if (raw) {
    if (typeof raw.imageCounts === "number") imageCounts = raw.imageCounts;
    else if (typeof raw.image_count === "number") imageCounts = raw.image_count;
    else if (typeof raw.count === "number") imageCounts = raw.count;
    else if (typeof raw.total === "number") imageCounts = raw.total;
    else if (Array.isArray((raw as any).specimens)) imageCounts = (raw as any).specimens.length;
  }

  const specimenData: SpecimenData = {
    species: speciesNameEncoded,
    imageCounts,
  };

  // If the specimens API didn't provide a count, fall back to the image
  // metadata endpoint which is already used elsewhere to enumerate image IDs.
  if (imageCounts === 0) {
    try {
      const metaResp = await fetch(
        `/api/images/metadata?scientificName=${encodeURIComponent(speciesNameEncoded)}`
      );
      if (metaResp.ok) {
        const meta = await metaResp.json();
        if (Array.isArray(meta)) {
          specimenData.imageCounts = meta.length;
        } else if (meta && Array.isArray((meta as any).imageIds)) {
          specimenData.imageCounts = (meta as any).imageIds.length;
        } else if (meta && Array.isArray((meta as any).images)) {
          specimenData.imageCounts = (meta as any).images.length;
        } else if (meta && typeof (meta as any).total === "number") {
          specimenData.imageCounts = (meta as any).total;
        }
      }
    } catch (err) {
      // ignore fallback failures; leave imageCounts as-is (0)
      // eslint-disable-next-line no-console
      console.debug("Specimen count fallback failed:", err);
    }
  }

  return specimenData;
}

export { fetchSpecimenData };
