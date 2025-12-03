/**
 * Fetches the thumbnail for a given species name from the API.
 * @param speciesName - The name of the species to fetch the image for.
 * @returns A promise that resolves to a local blob URL for the image.
 * @throws An error if the network response is not ok.
 */

const IMAGE_API_BASE = "/api/images";

function cleanSpeciesName(name: string): string {
  return name.toLowerCase().replace(/ /g, "_");
}

/**
 * Fetches the species image(s) ID(s) from the API.
 * @param speciesName
 */
async function fetchSpeciesImageIds(
  speciesName: string,
  limit: number
): Promise<string[]> {
  const cleanName = cleanSpeciesName(speciesName);
  const response = await fetch(
    `${IMAGE_API_BASE}/metadata?scientificName=${encodeURIComponent(cleanName)}`
  );

  if (!response.ok) {
    throw new Error(
      `Failed to fetch species image IDs. Status: ${response.status}`
    );
  }

  const data = await response.json();
  const ids = data as string[];
  if (!Array.isArray(ids)) {
    throw new Error("Invalid data format: imageIds is not an array");
  }
  if (ids.length > limit) {
    return ids.slice(0, limit);
  }
  return ids;
}

async function fetchSpeciesThumbnail(speciesName: string): Promise<string> {
  const cleanName = cleanSpeciesName(speciesName);
  return `${IMAGE_API_BASE}/species?scientificName=${encodeURIComponent(
    cleanName
  )}&type=thumbnail`;
}

async function fetchSpeciesImage(speciesName: string): Promise<string> {
  const cleanName = cleanSpeciesName(speciesName);
  // Construct the API endpoint URL
  return `${IMAGE_API_BASE}/species?scientificName=${encodeURIComponent(
    cleanName
  )}&type=full`;
}

async function fetchImgById(imageId: string): Promise<string> {
  return `${IMAGE_API_BASE}/id?imageId=${encodeURIComponent(
    imageId
  )}&type=full`;
}

async function fetchThumbnailById(imageId: string): Promise<string> {
  return `${IMAGE_API_BASE}/id?imageId=${encodeURIComponent(
    imageId
  )}&type=thumbnail`;
}

export {
  fetchSpeciesImageIds,
  fetchSpeciesImage,
  fetchSpeciesThumbnail,
  fetchImgById,
  fetchThumbnailById,
};
