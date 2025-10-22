const API_SERVICE_URL = `http://127.0.0.1:8000/taxon`;
/**
 * Fetches the thumbnail for a given species name from the API.
 * @param speciesName - The name of the species to fetch the image for.
 * @returns A promise that resolves to a local blob URL for the image.
 * @throws An error if the network response is not ok.
 */
export async function fetchSpeciesThumbnail(
  speciesName: string
): Promise<string> {
  // Force species name snake case
  const cleanName = speciesName.toLowerCase().replace(/ /g, "_");
  // Construct the API endpoint URL
  const response = await fetch(`${API_SERVICE_URL}/${cleanName}/thumbnail`);

  // Check if the request was successful
  if (!response.ok) {
    throw new Error(`Failed to fetch image. Status: ${response.status}`);
  }

  // The response is the image itself, so we read it as a blob
  const imageBlob = await response.blob();

  // Create a temporary URL from the blob to display the image
  const localUrl = URL.createObjectURL(imageBlob);

  return localUrl;
}

export async function fetchSpeciesImage(speciesName: string): Promise<string> {
  // Force species name snake case
  const cleanName = speciesName.toLowerCase().replace(/ /g, "_");
  // Construct the API endpoint URL
  const response = await fetch(`${API_SERVICE_URL}/${cleanName}/image`);

  // Check if the request was successful
  if (!response.ok) {
    throw new Error(`Failed to fetch image. Status: ${response.status}`);
  }

  // The response is the image itself, so we read it as a blob
  const imageBlob = await response.blob();

  // Create a temporary URL from the blob to display the image
  const localUrl = URL.createObjectURL(imageBlob);

  return localUrl;
}

export async function fetchImgById(imageId: string): Promise<string> {
  // Construct the API endpoint URL
  const response = await fetch(
    `http://127.0.0.1:8000/img-search/id/${imageId}`
  );

  // Check if the request was successful
  if (!response.ok) {
    throw new Error(
      `Failed to fetch similar images. Status: ${response.status}`
    );
  }

  // The response is expected to be a JSON array of image IDs
  const img_blob = await response.blob();
  const localUrl = URL.createObjectURL(img_blob);

  return localUrl;
}

export async function fetchThumbnailById(imageId: string): Promise<string> {
  // Construct the API endpoint URL
  const response = await fetch(
    `http://127.0.0.1:8000/img-search/id/${imageId}/thumbnail`
  );

  // Check if the request was successful
  if (!response.ok) {
    throw new Error(
      `Failed to fetch thumbnail image. Status: ${response.status}`
    );
  }

  // The response is the image itself, so we read it as a blob
  const imageBlob = await response.blob();

  // Create a temporary URL from the blob to display the image
  const localUrl = URL.createObjectURL(imageBlob);

  return localUrl;
}
