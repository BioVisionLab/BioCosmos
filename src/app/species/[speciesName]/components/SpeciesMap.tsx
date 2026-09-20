"use client";

import React, { useEffect, useState } from "react";
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
    // The same card as the classification above it: gradient header band over
    // a translucent body. The two sit stacked in the one narrow column, so
    // giving the map its own chrome made the column read as two unrelated
    // things.
    <div className="bg-linear-to-r from-white/50 to-white/30 dark:from-pacific-blue-900/30 dark:to-deep-mocha-800/50 rounded-xl backdrop-blur-lg">
      <div className="bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-t-xl">
        <h2 className="text-2xl font-semibold">Distribution Map</h2>
      </div>
      {/* Padding lives on the text, not on the body: the map runs edge to
          edge and its own bottom corners finish the card. */}
      <div>
        {loading ? (
          <div className="m-4 aspect-video bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-xl flex items-center justify-center">
            <TextLoading msg="Fetching GBIF occurrence data" />
          </div>
        ) : (
          <>
            {occurrences.length > 0 ? (
              // The count and the source belong in one line: both describe
              // what is plotted, and two stacked footnotes around a map read
              // as clutter.
              <p className="text-xs px-4 py-3 text-deep-mocha-700 dark:text-deep-mocha-300">
                Showing {occurrences.length} occurrences from{" "}
                <a
                  href="https://www.gbif.org/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-blue-700"
                >
                  GBIF
                </a>
                . Use the zoom and pan controls to explore the map.
              </p>
            ) : (
              <p className="text-xs px-4 py-3 text-deep-mocha-700 dark:text-deep-mocha-300">
                {emptyMessage(status)}
              </p>
            )}
            <SpeciesMap occurrences={occurrences} />
          </>
        )}
      </div>
    </div>
  );
}

export default SpeciesDistribution;
