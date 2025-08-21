import { API_HOST } from "./config";

const API_SERVICE_URL = `http://127.0.0.1:8000/taxon`;

const INITIAL_SPECIES = [
  "zeuxidia_doubledaii",
  "abananote_erinome",
  "abrota_ganga",
  "zeuxidia_luxerii",
  "zipaetis_saitis",
  "acidalia_adela",
  "zipaetis_scylax",
  "zischkaia_pacarus",
];

export interface SpeciesThumbnails {
  name: string;
  imageUrl: string;
}

// Get an initial list of species.
// Request image thumbnails from API/taxon/${speciesName}/thumbnail

export function getSpeciesList(): string[] {
  return INITIAL_SPECIES;
}

/**
 * Fetches the thumbnail for a given species name from the API.
 * @param speciesName - The name of the species to fetch the image for.
 * @returns A promise that resolves to a local blob URL for the image.
 * @throws An error if the network response is not ok.
 */
export const fetchSpeciesImage = async (
  speciesName: string
): Promise<string> => {
  // Construct the API endpoint URL
  const response = await fetch(`${API_SERVICE_URL}/${speciesName}/thumbnail`);

  // Check if the request was successful
  if (!response.ok) {
    throw new Error(`Failed to fetch image. Status: ${response.status}`);
  }

  // The response is the image itself, so we read it as a blob
  const imageBlob = await response.blob();

  // Create a temporary URL from the blob to display the image
  const localUrl = URL.createObjectURL(imageBlob);

  return localUrl;
};
