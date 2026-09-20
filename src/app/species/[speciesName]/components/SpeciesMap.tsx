"use client";

import React, { useEffect, useState } from "react";
import { GbifAttribution } from "../../../../components/Attribution";
import { GbifLookupStatus, Occurrence } from "@/lib/map";
import SpeciesMap from "@/components/SpeciesMap";
import { fetchGbifOccurrences } from "@/lib/map";
import { TextLoading } from "@/components/Loadings";

interface SpeciesDistributionProps {
  /** The name the collection records, which is also the page slug. */
  recordedName: string;
  /** What Catalogue of Life resolved it to, tried against GBIF first. */
  acceptedName?: string | null;
}

/**
 * What to say when the map has no points.
 *
 * "No occurrences" and "GBIF has never heard of this name" are different
 * facts, and only one of them is about the species.
 */
function emptyMessage(status: GbifLookupStatus): string {
  switch (status) {
    case "unmatched":
      return "This name was not found in the GBIF taxonomic backbone, so no occurrences could be retrieved.";
    case "error":
      return "GBIF could not be reached. Showing map without points.";
    default:
      return "No georeferenced GBIF occurrences found. Showing map without points.";
  }
}

function SpeciesDistribution({
  recordedName,
  acceptedName,
}: SpeciesDistributionProps) {
  const [occurrences, setOccurrences] = useState<Occurrence[]>([]);
  const [status, setStatus] = useState<GbifLookupStatus>("ok");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;

    const fetchOccurrences = async () => {
      setLoading(true);
      const result = await fetchGbifOccurrences(
        recordedName.trim(),
        acceptedName,
      );
      if (ignore) return;
      setOccurrences(result.occurrences);
      setStatus(result.status);
      setLoading(false);
    };

    void fetchOccurrences();
    return () => {
      ignore = true;
    };
  }, [recordedName, acceptedName]);

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-1">Distribution Map</h2>
      {loading ? (
        <div className="aspect-video bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-xl flex items-center justify-center">
          <TextLoading msg="Fetching GBIF occurrence data" />
        </div>
      ) : (
        <>
          {occurrences.length > 0 ? (
            <p className="text-xs mb-3 text-deep-mocha-700 dark:text-deep-mocha-300">
              Showing {occurrences.length} GBIF occurrences. Use the zoom and
              pan controls to explore the map.
            </p>
          ) : (
            <p className="text-xs mb-2 text-deep-mocha-700 dark:text-deep-mocha-300">
              {emptyMessage(status)}
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
