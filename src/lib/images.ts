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
  try {
    const response = await fetch(
      `/api/species-image?species=${encodeURIComponent(
        cleanName
      )}&type=thumbnail`
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch thumbnail. Status: ${response.status}`);
    }
    return URL.createObjectURL(await response.blob());
  } catch (error) {
    console.error(
      `Error fetching thumbnail for species ${speciesName}:`,
      error
    );
    throw error;
  }
}

export async function fetchSpeciesImage(speciesName: string): Promise<string> {
  const cleanName = speciesName.toLowerCase().replace(/ /g, "_");
  // Construct the API endpoint URL
  const response = await fetch(
    `/api/species-image?species=${encodeURIComponent(cleanName)}&type=full`
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch image. Status: ${response.status}`);
  }

  return URL.createObjectURL(await response.blob());
}

export async function fetchImgById(imageId: string): Promise<string> {
  try {
    const response = await fetch(
      `/api/image-id?imageId=${encodeURIComponent(imageId)}&type=full`
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch image. Status: ${response.status}`);
    }
    return URL.createObjectURL(await response.blob());
  } catch (error) {
    console.error(`Error fetching image for ID ${imageId}:`, error);
    throw error;
  }
}

export async function fetchThumbnailById(imageId: string): Promise<string> {
  try {
    const response = await fetch(
      `/api/image-id?imageId=${encodeURIComponent(imageId)}&type=thumbnail`
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch thumbnail. Status: ${response.status}`);
    }
    return URL.createObjectURL(await response.blob());
  } catch (error) {
    console.error(`Error fetching thumbnail for ID ${imageId}:`, error);
    throw error;
  }
}
