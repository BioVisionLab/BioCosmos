"use client"; // This component needs to be a client component
// cspell:ignore Gbif GBIF

import React, { useEffect, useState } from "react";
import { GbifAttribution } from "../../../../components/Attribution";
import { Occurrence } from "@/lib/map";
import SpeciesMap from "@/components/SpeciesMap";
import { fetchGbifOccurrences } from "@/lib/map";
import { TextLoading } from "@/components/Loadings";

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
          <TextLoading msg="Fetching GBIF occurrence data" />
        </div>
      ) : (
        <>
          {occurrences.length > 0 ? (
            <p className="text-xs mb-2 text-gray-700 dark:text-gray-300">
              Showing {occurrences.length} GBIF occurrences. Use the zoom and
              pan controls to explore the map.
            </p>
          ) : (
            <p className="text-xs mb-2 text-gray-700 dark:text-gray-300">
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
