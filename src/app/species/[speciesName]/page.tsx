import { getTaxonomyData } from "@/lib/speciesData"; // Import the function and the type
import Link from "next/link";
import TabsComponent from "./components/tabs";
import { Occurrence } from "@/lib/types";
import SpeciesHeader from "./components/title";

interface SpeciesPageProps {
  params: {
    speciesName: string; // This comes from the folder name [speciesName]
  };
}

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

// --- End GBIF API Fetching Function ---
export default async function SpeciesPage({ params }: SpeciesPageProps) {
  const resolvedParams = await params;
  const { speciesName: folderName } = resolvedParams;

  const taxonomyData = await getTaxonomyData(folderName);

  // Handle case where species data might not be found
  if (!taxonomyData) {
    return (
      <section className="container mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold mb-6">Species Not Found</h1>
        <p>The requested species ({folderName}) could not be found.</p>
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
    <section>
      {" "}
      {/* Removed container from here, relies on Layout's container */}
      {/* Updated Breadcrumbs including Genus */}
      <nav className="text-sm mb-4 text-gray-600 dark:text-gray-400 flex items-center gap-2">
        <Link href="/" className="hover:underline">
          Home
        </Link>
        <span>&gt;</span>
        {/* Link to Family (assuming Nymphalidae for now) */}
        <Link
          href={`/family/${taxonomyData.family}`}
          className="hover:underline"
        >
          {taxonomyData.family}
        </Link>
        <span>&gt;</span>
        {/* Link to the Genus page */}
        <Link
          href={`/genus/${taxonomyData.genus}`}
          className="hover:underline italic"
        >
          {taxonomyData.genus}
        </Link>
        <span>&gt;</span>
        <span className="italic text-gray-800 dark:text-gray-200">
          {taxonomyData.species}
        </span>
      </nav>
      {/* Optional: Add explicit "Back to Genus" link */}
      <div className="mb-4">
        <Link
          href={`/genus/${taxonomyData.genus}`}
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          &larr; Back to <span className="italic">{taxonomyData.genus}</span>{" "}
          species
        </Link>
      </div>
      <SpeciesHeader taxonomy={taxonomyData} name={taxonomyData.species} />
      <div>
        <TabsComponent
          speciesName={folderName}
          taxonomyData={taxonomyData}
          gbifOccurrences={gbifOccurrences}
        />
      </div>
    </section>
  );
}
