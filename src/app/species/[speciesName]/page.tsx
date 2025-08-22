import {
  getSpeciesData,
  getTaxonomyData,
  TaxonomyData,
} from "@/lib/speciesData"; // Import the function and the type
import Link from "next/link"; // For breadcrumbs
import SpeciesDetailMapWrapper from "@/components/SpeciesDetailMapWrapper";
import SpeciesImageGallery from "@/components/SpeciesImageGallery"; // Import the new gallery component
import { GbifAttribution } from "@/components/Attribution";
import { fetchSpeciesImage } from "@/lib/speciesList";
import Image from "next/image";

interface SpeciesPageProps {
  params: {
    speciesName: string; // This comes from the folder name [speciesName]
  };
}

// Define Occurrence type to match SpeciesMap component's expectation
interface Occurrence {
  key: string | number;
  decimalLatitude: number;
  decimalLongitude: number;
  // Add other fields as needed when fetching from GBIF
}

function RedListStatus({ statusCode }: { statusCode: string }) {
  let bgColor = "bg-gray-400";
  let textColor = "text-gray-900";
  let label = statusCode;
  switch (statusCode) {
    case "NE":
      bgColor = "bg-gray-300";
      textColor = "text-gray-900";
      label = "Not Evaluated";
      break;
    case "DD":
      bgColor = "bg-gray-200";
      textColor = "text-gray-900";
      label = "Data Deficient";
      break;
    case "LC":
      bgColor = "bg-green-200";
      textColor = "text-green-900";
      label = "Least Concern";
      break;
    case "NT":
      bgColor = "bg-yellow-200";
      textColor = "text-yellow-900";
      label = "Near Threatened";
      break;
    case "VU":
      bgColor = "bg-red-200";
      textColor = "text-red-900";
      label = "Vulnerable";
      break;
    case "EN":
      bgColor = "bg-orange-200";
      textColor = "text-orange-900";
      label = "Endangered";
      break;
    case "CR":
      bgColor = "bg-red-300";
      textColor = "text-red-900";
      label = "Critically Endangered";
      break;
    case "EX":
      bgColor = "bg-black";
      textColor = "text-white";
      label = "Extinct";
      break;
    case "EW":
      bgColor = "bg-gray-500";
      textColor = "text-white";
      label = "Extinct in the Wild";
      break;
  }
  return (
    <div>
      <h2 className="text-2xl font-semibold mb-2">IUCN RedList Status</h2>
      <span
        className={`px-2 py-0.5 rounded-full text-xs font-medium ${bgColor} ${textColor}`}
      >
        {label}
      </span>
    </div>
  );
}

// Whenever available, we use the combination
// of species name and authorship for the title
// If taxonomy data is not available, we fall back to the species name only
// We used the name from the images
function SpeciesTitle({
  taxonomy,
  name,
}: {
  taxonomy: TaxonomyData | null;
  name: string;
}) {
  if (taxonomy === null) {
    return <span className="italic">{name}</span>;
  }

  const authorship = taxonomy.authorship ? taxonomy.authorship.trim() : "";
  const species = taxonomy.species ? taxonomy.species.trim() : "";

  return (
    <span>
      <span className="italic">{species}</span>
      {authorship !== null && authorship !== "" ? " " + authorship : null}
    </span>
  );
}

function CommonName({
  vernacularName,
  commonName,
}: {
  vernacularName: string | null;
  commonName: string;
}) {
  const name = vernacularName ?? commonName;

  return <p className="text-xl text-gray-700 dark:text-gray-300">{name}</p>;
}

function SpeciesDescriptionText({
  description,
  species,
}: {
  description: string | null;
  species: string;
}) {
  if (!description || description.trim() === "") {
    return (
      <p className="text-gray-500 dark:text-gray-400 mt-2">
        No description available for <i>{species}</i>.
      </p>
    );
  }
  return (
    <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
      {description}
    </p>
  );
}

function SpeciesDescription({
  description,
  species,
}: {
  description: string | null;
  species: string;
}) {
  return (
    <div>
      <h2 className="text-2xl font-semibold mt-4">Description</h2>
      <SpeciesDescriptionText description={description} species={species} />
    </div>
  );
}

function SpeciesClassification({
  taxonomyData,
}: {
  taxonomyData: TaxonomyData | null;
}) {
  if (!taxonomyData) {
    return (
      <p className="text-gray-500 dark:text-gray-400">
        No classification data available.
      </p>
    );
  }

  return (
    <div className="-mt-1">
      <h2 className="text-2xl font-semibold mb-2">Classification</h2>
      <table className="text-sm text-gray-700 dark:text-gray-300 w-full min-w-[350px]">
        <tbody>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Kingdom</td>
            <td className="break-all">
              : {taxonomyData?.kingdom ?? "Unknown"}
            </td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Phylum</td>
            <td className="break-all">: {taxonomyData?.phylum ?? "Unknown"}</td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Class</td>
            <td className="break-all">: {taxonomyData?.class ?? "Unknown"}</td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Order</td>
            <td className="break-all">: {taxonomyData?.order ?? "Unknown"}</td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Family</td>
            <td className="break-all">: {taxonomyData?.family ?? "Unknown"}</td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Genus</td>
            <td className="break-all">
              : <i className="italic">{taxonomyData?.genus ?? "Unknown"}</i>
            </td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Species</td>
            <td className="break-all">
              : <i className="italic">{taxonomyData?.species ?? "Unknown"}</i>
            </td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Authorship</td>
            <td className="break-all">
              : {taxonomyData?.authorship ?? "Unknown"}
            </td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top my-2">
              Taxonomic Status
            </td>
            <td className="break-all">
              : {taxonomyData?.taxonomicStatus ?? "Unknown"}
            </td>
          </tr>
        </tbody>
      </table>
      <GbifAttribution />
    </div>
  );
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

  const thumbnail: string = await fetchSpeciesImage(taxonomyData.species);
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
      {/* Main Title Area */}
      <div className="mb-6">
        {/* Revert color classes on scientific name */}
        <h1 className="text-4xl font-bold mb-1">
          <SpeciesTitle taxonomy={taxonomyData} name={taxonomyData.species} />
        </h1>
        {/* Revert color classes on common name */}
        <CommonName
          vernacularName={taxonomyData.vernacularName ?? null}
          commonName={taxonomyData.vernacularName ?? "Unknown Species"}
        />
        {/* Reverted to original gray colors */}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Use SpeciesImageGallery Component */}
        <div className="lg:col-span-2">
          <Image
            src={thumbnail}
            alt={`Species Thumbnail`}
            width={150}
            height={150}
            className="m-2"
          />
          {/* <SpeciesImageGallery
            speciesName={taxonomyData.species}
            mainImageUrl={thumbnails}
            allImageUrls={thumbnails}
          />
          <SpeciesDescription
            description={taxonomyData?.description ?? description}
            species={taxonomyData?.species ?? name} // Use species from taxonomy or fallback to name
          /> */}
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
    </section>
  );
}
