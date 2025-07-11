import fs from "fs";
import path from "path";

import { API_HOST } from "./config";
import { int } from "zod/v4";

const TAXONOMY_SERVICE_URL = `${API_HOST}/taxon`;

// Define the richer return type for clarity
export interface SpeciesData {
  // Exporting interface for use elsewhere
  name: string; // Scientific name (e.g., Genus species)
  commonName: string; // Simulated common name
  imageUrl: string; // First image URL
  allImageUrls: string[]; // All image URLs for the species
  originalFolderName: string;
  taxonomy: {
    kingdom: string;
    phylum: string;
    class: string;
    order: string;
    family: string;
    genus: string;
    species: string;
  };
  description: string; // Placeholder description
  conservationStatus: string; // Placeholder status
}

export interface TaxonomyData {
  kingdom: string;
  phylum: string;
  class: string;
  order: string;
  family: string;
  genus: string;
  species: string;
  authorship: string;
  vernacularName: string;
  description: string;
  redlistCategory: string;
  taxonomicStatus: string;
}

// --- Static Data Store ---
// Add more species here following the pattern:
// 'folder_name_lowercase': { commonName: "...", description: "...", conservationStatus: "..." }
const staticSpeciesData: Record<
  string,
  { commonName: string; description: string; conservationStatus: string }
> = {
  danaus_plexippus: {
    commonName: "Monarch Butterfly",
    description:
      "The Monarch butterfly is known for its incredible long-distance seasonal migration. Larvae feed exclusively on milkweed plants, sequestering toxins that make the adults unpalatable to predators. Its distinct orange and black wing pattern is easily recognizable.",
    conservationStatus: "Endangered", // IUCN status as of recent assessments
  },
  vanessa_atalanta: {
    commonName: "Red Admiral",
    description:
      "The Red Admiral is a familiar butterfly found in temperate regions across Europe, Asia, and North America. It is characterized by its velvety black wings intersected by prominent reddish-orange bands and white spots. Adults often feed on fermenting fruit and tree sap.",
    conservationStatus: "Least Concern",
  },
  ypthima_baldus: {
    commonName: "Common Five-ring",
    description:
      "The Common Five-ring is a widespread butterfly found across parts of Asia and Australia. It typically flies close to the ground in grassy areas and is characterized by several prominent eyespots ('rings') on its wings.",
    conservationStatus: "Least Concern",
  },
  zaretis_itys: {
    commonName: "Itys Leafwing",
    description:
      "The Itys Leafwing is known for its remarkable camouflage, resembling a dead leaf when its wings are closed. Found in Central and South America, it inhabits forest environments. The underside wing pattern provides excellent protection from predators.",
    conservationStatus: "Least Concern", // General assumption, may vary locally
  },
  // Add more species data here...
};
// --- End Static Data Store ---

// Helper function to process a single species folder
function processSpeciesFolder(
  folderName: string,
  baseImageDir: string
): SpeciesData | null {
  const speciesFolderPath = path.join(baseImageDir, folderName);
  let imageFiles: string[] = [];

  try {
    imageFiles = fs
      .readdirSync(speciesFolderPath)
      .filter((file) => /\.jpe?g|\.png|\.webp$/i.test(file));
  } catch (err) {
    // Gracefully handle cases where the directory might not exist or is unreadable
    if ((err as NodeJS.ErrnoException).code !== "ENOENT") {
      console.warn(`Could not read directory: ${speciesFolderPath}`, err);
    }
    return null; // Skip this species
  }

  if (imageFiles.length === 0) return null; // Skip if no images found

  const firstImage = imageFiles[0];
  const allImageUrls = imageFiles.map(
    (file) => `/images/nymphalidae_new/${folderName}/${file}`
  );

  // Format species name and extract Genus/species
  let formattedName = folderName;
  let genus = "Unknown";
  let species = "sp.";
  const parts = folderName.split("_");
  if (parts.length === 2) {
    genus = parts[0].charAt(0).toUpperCase() + parts[0].slice(1).toLowerCase();
    species = parts[1].toLowerCase();
    formattedName = `${genus} ${species}`;
  } else {
    formattedName = folderName
      .replace(/_/g, " ")
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(" ");
    genus = formattedName.split(" ")[0] || genus;
  }

  // --- Look up static data ---
  const lowerCaseFolderName = folderName.toLowerCase();
  const staticData = staticSpeciesData[lowerCaseFolderName];

  // --- Determine final values ---
  const commonName =
    staticData?.commonName ??
    formattedName
      .replace(/^[A-Z]+\s/, "")
      .replace(/^\w/, (c) => c.toUpperCase()) + " Butterfly";
  const description = staticData?.description ?? "";
  const conservationStatus =
    staticData?.conservationStatus ??
    ["Least Concern", "Near Threatened", "Vulnerable"][
      Math.floor(Math.random() * 3)
    ];

  return {
    name: formattedName,
    commonName: commonName, // Use determined common name
    imageUrl: `/images/nymphalidae_new/${folderName}/${firstImage}`,
    allImageUrls: allImageUrls,
    originalFolderName: folderName,
    taxonomy: {
      kingdom: "Animalia",
      phylum: "Arthropoda",
      class: "Insecta",
      order: "Lepidoptera",
      family: "Nymphalidae", // Assuming all are Nymphalidae based on folder
      genus: genus,
      species: species,
    },
    description: description, // Use determined description
    conservationStatus: conservationStatus, // Use determined status
  };
}

// --- New Function: Get List of Genera ---
export interface GenusSummary {
  name: string;
  representativeImageUrl: string | null;
}

export async function getGenusList(
  familyName: string = "Nymphalidae"
): Promise<GenusSummary[]> {
  // For now, we assume we only care about Nymphalidae from our directory
  // In a more complex setup, you might filter based on the familyName argument
  if (familyName.toLowerCase() !== "nymphalidae") {
    console.warn(
      `getGenusList currently only supports Nymphalidae, requested: ${familyName}`
    );
    return [];
  }

  const allSpecies = await getSpeciesData(); // Get all species data

  const generaMap = new Map<string, string | null>(); // Map genus name to image URL

  // Sort species alphabetically by name to ensure consistent image selection
  allSpecies.sort((a, b) => a.name.localeCompare(b.name));

  for (const species of allSpecies) {
    const genusName = species.taxonomy.genus;
    if (!generaMap.has(genusName)) {
      // If this is the first time seeing this genus, store its image URL
      generaMap.set(genusName, species.imageUrl);
    }
  }

  // Convert map to the desired array format
  const genusList: GenusSummary[] = Array.from(generaMap.entries()).map(
    ([name, imageUrl]) => ({
      name: name,
      representativeImageUrl: imageUrl,
    })
  );

  // Sort genera alphabetically by name
  genusList.sort((a, b) => a.name.localeCompare(b.name));

  console.log(`Found ${genusList.length} genera in ${familyName}`);
  return genusList;
}
// --- End New Function: Get List of Genera ---

// --- New Function: Get Species by Genus ---
export async function getSpeciesByGenus(
  genusName: string
): Promise<SpeciesData[]> {
  const allSpecies = await getSpeciesData(); // Get all species data
  const filteredSpecies = allSpecies.filter(
    (species) =>
      species.taxonomy.genus.toLowerCase() === genusName.toLowerCase()
  );
  console.log(`Found ${filteredSpecies.length} species in genus ${genusName}`);
  return filteredSpecies;
}
// --- End New Function: Get Species by Genus ---

export async function getTaxonomyData(
  folderName: string
): Promise<TaxonomyData | null> {
  // We will capture the species name from the folder name by splitting on underscores
  let genus = "Unknown";
  let species = "sp.";
  const parts = folderName.split("_");
  if (parts.length === 2) {
    genus = parts[0].charAt(0).toUpperCase() + parts[0].slice(1).toLowerCase();
    species = parts[1].toLowerCase();
  }
  const formattedName = `${genus} ${species}`;

  // Fetch taxonomy data from the external service
  try {
    const response = await fetch(
      `${TAXONOMY_SERVICE_URL}?q=${encodeURIComponent(formattedName)}`
    );
    if (!response.ok) {
      console.error(
        `Failed to fetch taxonomy data for ${formattedName}: ${response.statusText}`
      );
      return null; // Return null if the request fails
    }
    const dataRaw = await response.json();
    const data = dataRaw["taxonomy"] || dataRaw; // Handle different response structures
    console.log(`Fetched taxonomy data for ${formattedName}:`, data);
    if (!data) {
      console.warn(`No taxonomy data found for ${formattedName}`);
      return null; // Return null if no data is found
    }
    // Map the response to our SpeciesData format
    return {
      kingdom: data.kingdom || "Animalia",
      phylum: data.phylum || "Arthropoda",
      class: data.class || "Insecta",
      order: data.order || "Lepidoptera",
      family: data.family || "Nymphalidae", // Default to Nymphalidae
      genus: data.genus || genus,
      species: data.species || species,
      authorship: data.authorship || formattedName,
      vernacularName: data.vernacularName || formattedName, // Fallback to formatted name
      description: data.description,
      redlistCategory: data.redlistCategory || "Unknown", // Default status
      taxonomicStatus: data.taxonomicStatus || "Accepted", // Default status
    };
  } catch (error) {
    console.error(`Error fetching taxonomy data for ${formattedName}:`, error);
    return null; // Return null if there was an error
  }
}
// Overload signatures for type safety
export async function getSpeciesData(): Promise<SpeciesData[]>;
export async function getSpeciesData(
  folderName: string
): Promise<SpeciesData | null>;

// Combined function implementation
export async function getSpeciesData(
  folderName?: string
): Promise<SpeciesData[] | SpeciesData | null> {
  const baseImageDir = path.join(
    process.cwd(),
    "public",
    "images",
    "nymphalidae_new"
  );

  if (folderName) {
    // Request for a single species
    return processSpeciesFolder(folderName, baseImageDir);
  } else {
    // Request for all species
    let allSpeciesData: SpeciesData[] = [];
    try {
      const speciesFolders = fs
        .readdirSync(baseImageDir, { withFileTypes: true })
        .filter((dirent) => dirent.isDirectory())
        .map((dirent) => dirent.name);

      allSpeciesData = speciesFolders
        .map((folder) => processSpeciesFolder(folder, baseImageDir))
        .filter((data): data is SpeciesData => data !== null); // Type guard to filter out nulls
    } catch (err) {
      console.error("Error reading base species directory:", err);
      return []; // Return empty array on error
    }
    return allSpeciesData;
  }
}
