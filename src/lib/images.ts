/**
 * Fetches the thumbnail for a given species name from the API.
 * @param speciesName - The name of the species to fetch the image for.
 * @returns A promise that resolves to a local blob URL for the image.
 * @throws An error if the network response is not ok.
 */
export async function fetchSpeciesThumbnail(
  speciesName: string
): Promise<string> {
  const cleanName = speciesName.toLowerCase().replace(/ /g, "_");
  return `/api/species-image?species=${encodeURIComponent(
    cleanName
  )}&type=thumbnail`;
}

export async function fetchSpeciesImage(speciesName: string): Promise<string> {
  const cleanName = speciesName.toLowerCase().replace(/ /g, "_");
  // Construct the API endpoint URL
  return `/api/species-image?species=${encodeURIComponent(
    cleanName
  )}&type=full`;
}

export async function fetchImgById(imageId: string): Promise<string> {
  return `/api/image-id?imageId=${encodeURIComponent(imageId)}&type=full`;
}

export async function fetchThumbnailById(imageId: string): Promise<string> {
  return `/api/image-id?imageId=${encodeURIComponent(imageId)}&type=thumbnail`;
}
