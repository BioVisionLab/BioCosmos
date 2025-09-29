import { cleanSpeciesName } from "./names";

const API_SERVICE_URL = `http://127.0.0.1:8000/taxon`;

const INITIAL_SPECIES = [
  "anaeomorpha_splendida",
  "agrias_narcissus",
  "athyma_libnites",
  "euploea_eleusina",
  "nessaea_hewitsonii",
  "zeuxidia_ameythystus",
  "panacea_prola",
  "charaxes_subornatus",
  "agrias_phalcidon",
];

// Get an initial list of species.
// Request image thumbnails from API/taxon/${speciesName}/thumbnail

export function getSpeciesList(): string[] {
  // We shuffle the initial species array to get a random selection each time
  // return six random species from the list
  const sorted_list = INITIAL_SPECIES.sort(() => 0.5 - Math.random());
  return sorted_list.slice(0, 6).sort();
}

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

// NEW FUNCTION W/ SEVERAL IMAGES: IN PROGRESS
// (nonfunctional, always falls back to single blob image)
export async function fetchSpeciesImage(
  speciesName: string
): Promise<string[]> {
  // Force species name snake case
  const cleanName = speciesName.toLowerCase().replace(/ /g, "_");

  // Attempt to fetch JSON image list first
  try {
    // Calling the API endpoint "/taxon/{species_name}/ids"
    const listResponse = await fetch(`${API_SERVICE_URL}/${cleanName}/ids`);
    if (listResponse.ok) {
      const data = await listResponse.json();

      // Handle array of strings OR array of objects with "url"
      const urls = Array.isArray(data)
        ? data
            .map((item: any) => (typeof item === "string" ? item : item.url))
            .filter(Boolean)
        : [];

      if (urls.length > 0) {
        return urls;
      }
    }
  } catch (err) {
    console.warn("No image list endpoint, falling back to single image:", err);
  }
  // Fallback: single blob image endpoint
  const response = await fetch(`${API_SERVICE_URL}/${cleanName}/image`);
  if (!response.ok) {
    throw new Error(`Failed to fetch image. Status: ${response.status}`);
  }
  const imageBlob = await response.blob();
  const localUrl = URL.createObjectURL(imageBlob);
  return [localUrl]; // wrap single image in array
}

/* OLD FUNCTION: ONE IMAGE DISPLAYS (functional)
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
  */

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
