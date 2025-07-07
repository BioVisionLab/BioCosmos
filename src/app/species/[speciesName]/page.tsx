import Image from "next/image";
// Removed fs/path imports as data fetching is now in lib
// import fs from 'fs';
// import path from 'path';
import {
  getSpeciesData,
  getTaxonomyData,
  SpeciesData,
} from "@/lib/speciesData"; // Import the function and the type
import Link from "next/link"; // For breadcrumbs
// Remove dynamic import
// import dynamic from 'next/dynamic';
// Import the new wrapper component
import SpeciesDetailMapWrapper from "@/components/SpeciesDetailMapWrapper";
import SpeciesImageGallery from "@/components/SpeciesImageGallery"; // Import the new gallery component
import { de } from "zod/v4/locales";

interface SpeciesPageProps {
  params: {
    speciesName: string; // This comes from the folder name [speciesName]
  };
}

// Remove dynamic import definition for SpeciesMap
/*
const SpeciesMap = dynamic(() => import('@/components/SpeciesMap'), { 
  ssr: false, 
  loading: () => ...
});
*/

// Define Occurrence type to match SpeciesMap component's expectation
interface Occurrence {
  key: string | number;
  decimalLatitude: number;
  decimalLongitude: number;
  // Add other fields as needed when fetching from GBIF
}

// Helper function to format conservation status (optional styling)
function formatConservationStatus(statusCode: string) {
  let bgColor = "bg-gray-400";
  let textColor = "text-gray-900";
  let label = statusCode;
  switch (statusCode) {
    case "NE": // Not Evaluated
      bgColor = "bg-gray-300";
      textColor = "text-gray-900";
      label = "Not Evaluated";
      break;
    case "DD": // Data Deficient
      bgColor = "bg-gray-200";
      textColor = "text-gray-900";
      label = "Data Deficient";
      break;
    case "LC": // Least Concern
      bgColor = "bg-green-200";
      textColor = "text-green-900";
      label = "Least Concern";
      break;
    case "NT": // Near Threatened
      bgColor = "bg-yellow-200";
      textColor = "text-yellow-900";
      label = "Near Threatened";
      break;
    case "VU": // Vulnerable
      bgColor = "bg-red-200";
      textColor = "text-red-900";
      label = "Vulnerable";
      break;
    case "EN": // Endangered
      bgColor = "bg-orange-200";
      textColor = "text-orange-900";
      label = "Endangered";
      break;
    case "CR": // Critically Endangered
      bgColor = "bg-red-300";
      textColor = "text-red-900";
      label = "Critically Endangered";
      break;
    case "EX": // Extinct
      bgColor = "bg-black";
      textColor = "text-white";
      label = "Extinct";
      break;
    case "EW": // Extinct in the Wild
      bgColor = "bg-gray-500";
      textColor = "text-white";
      label = "Extinct in the Wild";
      break;
    // Add more cases as needed
  }
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-medium ${bgColor} ${textColor}`}
    >
      {label}
    </span>
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
    const occurrences = data.results
      .map((occ: any) => ({
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

  // Fetch the single species data using the updated function
  const details = await getSpeciesData(folderName);

  // Handle case where species data might not be found
  if (!details) {
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

  // Now we know details is not null and has the SpeciesData type
  const { name, commonName, description, taxonomy, imageUrl, allImageUrls } =
    details;

  const taxonomyData = await getTaxonomyData(folderName);
  // Fetch GBIF data using the scientific name
  const gbifOccurrences = await fetchGbifOccurrences(name); // Use the fetched scientific name

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
        <Link href={`/family/${taxonomy.family}`} className="hover:underline">
          {taxonomy.family}
        </Link>
        <span>&gt;</span>
        {/* Link to the Genus page */}
        <Link
          href={`/genus/${taxonomy.genus}`}
          className="hover:underline italic"
        >
          {taxonomy.genus}
        </Link>
        <span>&gt;</span>
        <span className="italic text-gray-800 dark:text-gray-200">
          {taxonomy.species}
        </span>
      </nav>
      {/* Optional: Add explicit "Back to Genus" link */}
      <div className="mb-4">
        <Link
          href={`/genus/${taxonomy.genus}`}
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          &larr; Back to <span className="italic">{taxonomy.genus}</span>{" "}
          species
        </Link>
      </div>
      {/* Main Title Area */}
      <div className="mb-6">
        {/* Revert color classes on scientific name */}
        <h1 className="text-4xl font-bold italic mb-1">{name}</h1>
        {/* Revert color classes on common name */}
        <p className="text-xl text-gray-700 dark:text-gray-300">
          {commonName}
        </p>{" "}
        {/* Reverted to original gray colors */}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Use SpeciesImageGallery Component */}
        <div className="lg:col-span-2">
          <SpeciesImageGallery
            speciesName={name}
            mainImageUrl={imageUrl}
            allImageUrls={allImageUrls}
          />
        </div>

        {/* Right Column: Details */}
        <div className="lg:col-span-1 space-y-6">
          {/* Description Section */}
          <div>
            <h2 className="text-2xl font-semibold mb-2">Description</h2>
            <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
              {taxonomyData?.description &&
              taxonomyData.description.trim() !== "" ? (
                taxonomyData.description
              ) : (
                <>
                  No description available for <i>{name}</i>.
                </>
              )}
            </p>
          </div>

          {/* Taxonomy Section */}
          <div>
            <h2 className="text-2xl font-semibold mb-2">Classification</h2>
            <ul className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
              <li>
                <span className="font-medium w-20 inline-block">Kingdom:</span>{" "}
                {taxonomyData?.taxonomy?.kingdom ?? "Unknown"}
              </li>
              <li>
                <span className="font-medium w-20 inline-block">Phylum:</span>{" "}
                {taxonomyData?.taxonomy?.phylum ?? "Unknown"}
              </li>
              <li>
                <span className="font-medium w-20 inline-block">Class:</span>{" "}
                {taxonomyData?.taxonomy?.class ?? "Unknown"}
              </li>
              <li>
                <span className="font-medium w-20 inline-block">Order:</span>{" "}
                {taxonomy.order}
              </li>
              <li>
                <span className="font-medium w-20 inline-block">Family:</span>{" "}
                {taxonomy.family}
              </li>
              <li>
                <span className="font-medium w-20 inline-block">Genus:</span>{" "}
                <i className="italic">{taxonomy.genus}</i>
              </li>
              <li>
                <span className="font-medium w-20 inline-block">Species:</span>{" "}
                <i className="italic">{taxonomy.species}</i>
              </li>
            </ul>
          </div>

          {/* Conservation Status */}
          <div>
            <h2 className="text-2xl font-semibold mb-2">Status</h2>
            {formatConservationStatus(
              taxonomyData?.conservationStatus ?? "Unknown"
            )}
            {/* Display conservation status with optional styling */}
          </div>

          {/* Map Section - Use Wrapper Component */}
          <div>
            <h2 className="text-2xl font-semibold mb-2">Distribution Map</h2>
            {/* Render the wrapper component, passing fetched occurrences */}
            <SpeciesDetailMapWrapper occurrences={gbifOccurrences} />
            {/* Update the text to reflect actual data source */}
            <p className="text-xs text-gray-500 mt-1">
              {gbifOccurrences.length > 0
                ? `Displaying ${gbifOccurrences.length} occurrences from GBIF.`
                : "Occurrence data from GBIF (none found or error fetching)."}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

// Optional: Re-enable static generation if performance becomes an issue
// export async function generateStaticParams() { ... }
