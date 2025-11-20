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
  limit?: number,
  offset?: number
): Promise<string[]> {
  const cleanName = cleanSpeciesName(speciesName);
  // pass limit/offset to the server so it can control how many IDs are returned
  const qs: string[] = [];
  if (typeof limit === "number") qs.push(`limit=${encodeURIComponent(String(limit))}`);
  if (typeof offset === "number") qs.push(`offset=${encodeURIComponent(String(offset))}`);
  const qsStr = qs.length > 0 ? `&${qs.join("&")}` : "";
  const response = await fetch(
    `${IMAGE_API_BASE}/metadata?scientificName=${encodeURIComponent(cleanName)}${qsStr}`
  );

  if (!response.ok) {
    throw new Error(
      `Failed to fetch species image IDs. Status: ${response.status}`
    );
  }

  const data = await response.json();
  const ids = data["imageIds"] as string[];
  if (!Array.isArray(ids)) {
    throw new Error("Invalid data format: imageIds is not an array");
  }
  // Defensive: server should respect the requested `limit`, but slice client-side
  // as a fallback if a larger list is returned.
  if (typeof limit === "number" && ids.length > limit) {
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
