import { API_HOST } from "./config";

const API_SERVICE_URL = `http://127.0.0.1:8000/taxon`;

const INITIAL_SPECIES = [
  "zeuxidia_doubledaii",
  "abananote_erinome",
  "abrota_ganga",
  "zeuxidia_luxerii",
  "zipaetis_saitis",
  "acidalia_adela",
];

export interface SpeciesThumbnails {
  name: string;
  imageUrl: string;
  folderName: string;
}

// Get an initial list of species.
// Request image thumbnails from API/taxon/${speciesName}/thumbnail

function getSpeciesList(): string[] {
  return INITIAL_SPECIES.sort();
}

/**
 * Cleans the species name by replacing underscores with spaces.
 * Make it in sentence case.
 * @param name - The species name to clean.
 * @returns The cleaned species name.
 */
function clean_species_name(name: string): string {
  const [genus, ...rest] = name.replace(/_/g, " ").split(" ");
  return [genus.charAt(0).toUpperCase() + genus.slice(1), ...rest].join(" ");
}

/**
 * Fetches the thumbnail for a given species name from the API.
 * @param speciesName - The name of the species to fetch the image for.
 * @returns A promise that resolves to a local blob URL for the image.
 * @throws An error if the network response is not ok.
 */
export async function fetchSpeciesImage(speciesName: string): Promise<string> {
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
}

export async function getInitialSpeciesList(): Promise<SpeciesThumbnails[]> {
  const speciesList = getSpeciesList();
  const thumbnails = await Promise.all(
    speciesList.map(async (species) => {
      const imageUrl = await fetchSpeciesImage(species);
      return {
        name: clean_species_name(species),
        imageUrl,
        folderName: species,
      };
    })
  );
  return thumbnails;
}
