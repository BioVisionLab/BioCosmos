"use client"; // This component needs to be a client component
// cspell:ignore Gbif GBIF

import React, { useEffect, useState } from "react";
import { GbifAttribution } from "../../../../components/Attribution";
import { Occurrence } from "@/lib/types";
import SpeciesMap from "@/components/SpeciesMap";

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

function SpeciesDistribution({ speciesName }: { speciesName: string }) {
  const [occurrences, setOccurrences] = useState<Occurrence[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchOccurrences = async () => {
      setLoading(true);
      const data = await fetchGbifOccurrences(speciesName.trim());
      setOccurrences(data);
      setLoading(false);
    };
    fetchOccurrences();
  }, [speciesName]);

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-2">Distribution Map</h2>
      {loading ? (
        <div className="aspect-video bg-gray-200 dark:bg-gray-700 rounded flex items-center justify-center">
          <span className="text-gray-500">
            Fetching GBIF occurrence data...
          </span>
        </div>
      ) : (
        <>
          {occurrences.length > 0 ? (
            <p className="text-sm mb-2 text-gray-700 dark:text-gray-300">
              Showing {occurrences.length} occurrences. Use the zoom and pan
              controls to explore the map.
            </p>
          ) : (
            <p className="text-sm mb-2 text-gray-700 dark:text-gray-300">
              No GBIF occurrences found. Showing map without points.
            </p>
          )}
          <SpeciesMap occurrences={occurrences} />
          <GbifAttribution leadingText="Occurrence data provided by" />
        </>
      )}
    </div>
  );
}

export default SpeciesDistribution;
