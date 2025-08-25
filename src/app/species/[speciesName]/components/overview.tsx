import { getTaxonomyData } from "@/lib/speciesData";
import Link from "next/link";
import { SpeciesImages } from "./image_gallery";
import { SpeciesDescription } from "./description";
import { SpeciesClassification } from "./classification";
import { RedListStatus } from "./redlist_status";
import SpeciesDetailMapWrapper from "@/components/SpeciesDetailMapWrapper";

// Define Occurrence type to match SpeciesMap component's expectation
interface Occurrence {
  key: string | number;
  decimalLatitude: number;
  decimalLongitude: number;
  // Add other fields as needed when fetching from GBIF
}

// --- GBIF API Fetching Function ---
async function fetchGbifOccurrences(
  scientificName: string
): Promise<Occurrence[]> {
  // Basic check for valid name format
  if (!scientificName || !scientificName.includes(" ")) {
    console.warn(`Invalid scientific name for GBIF lookup: ${scientificName}`);
    return [];
  }

  // Construct the GBIF API URL (limit to 200 results for performance)
  // Using hasCoordinate=true and hasGeospatialIssue=false for cleaner data
  const gbifLimit = 200;
  const gbifApiUrl = `https://api.gbif.org/v1/occurrence/search?scientificName=${encodeURIComponent(
    scientificName
  )}&limit=${gbifLimit}&hasCoordinate=true&hasGeospatialIssue=false`;

  console.log(`Fetching GBIF data from: ${gbifApiUrl}`); // Log the URL for debugging

  try {
    const response = await fetch(gbifApiUrl, {
      // Optional: Add cache control if needed, but default Next.js fetch caching is usually sufficient
      // next: { revalidate: 3600 * 24 } // Example: revalidate once per day
    });

    if (!response.ok) {
      throw new Error(
        `GBIF API error: ${response.status} ${response.statusText}`
      );
    }

    const data = await response.json();

    // Process results: Filter out occurrences without valid lat/lon
    interface GbifRawOccurrence {
      key: string | number;
      decimalLatitude: number;
      decimalLongitude: number;
    }

    const occurrences = data.results
      .map((occ: GbifRawOccurrence) => ({
        key: occ.key, // GBIF unique key for the occurrence
        decimalLatitude: occ.decimalLatitude,
        decimalLongitude: occ.decimalLongitude,
      }))
      .filter(
        (occ: Occurrence) =>
          typeof occ.decimalLatitude === "number" &&
          typeof occ.decimalLongitude === "number" &&
          !isNaN(occ.decimalLatitude) &&
          !isNaN(occ.decimalLongitude)
      );

    console.log(
      `Fetched ${occurrences.length} valid GBIF occurrences for ${scientificName}`
    );
    return occurrences;
  } catch (error) {
    console.error(
      `Error fetching GBIF occurrences for ${scientificName}:`,
      error
    );
    return []; // Return empty array on error
  }
}

export async function SpeciesOverview({
  speciesName,
}: {
  speciesName: string;
}) {
  // Fetch taxonomy data
  const taxonomyData = await getTaxonomyData(speciesName);

  // Handle case where species data might not be found
  if (!taxonomyData) {
    return (
      <section className="container mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold mb-6">Species Not Found</h1>
        <p>The requested species ({speciesName}) could not be found.</p>
        <Link
          href="/"
          className="text-blue-600 hover:underline mt-4 inline-block"
        >
          Return to homepage
        </Link>
      </section>
    );
  }

  const gbifOccurrences = await fetchGbifOccurrences(taxonomyData.species);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-2">
        <SpeciesImages speciesName={speciesName} />
        <SpeciesDescription
          description={taxonomyData?.description ?? "No description available."}
          species={taxonomyData?.species ?? name} // Use species from taxonomy or fallback to name
        />
      </div>

      {/* Right Column: Details */}
      <div className="lg:col-span-1 space-y-6">
        <SpeciesClassification taxonomyData={taxonomyData} />
        <RedListStatus
          statusCode={taxonomyData?.redlistCategory ?? "Unknown"}
        />
        <div>
          <h2 className="text-2xl font-semibold mb-2">Distribution Map</h2>
          <p className="text-sm mb-2 text-gray-700 dark:text-gray-300">
            {gbifOccurrences.length > 0
              ? `Showing ${gbifOccurrences.length} occurrences. Use the zoom and pan controls to explore the map.`
              : "No occurrence data found."}
          </p>
          <SpeciesDetailMapWrapper occurrences={gbifOccurrences} />
        </div>
      </div>
    </div>
  );
}
