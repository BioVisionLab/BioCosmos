"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  fetchGbifTaxon,
  fetchSpeciesCoordinates,
  GbifTaxonResult,
  SpeciesCoordinates,
} from "@/lib/map";
import SpeciesMap, {
  MARKER_COLORS,
  markerKind,
  MarkerKind,
} from "@/components/SpeciesMap";
import { DistributionMapSkeleton } from "./DistributionMapSkeleton";

interface SpeciesDistributionProps {
  /** The name the collection records, which is also the page slug. */
  recordedName: string;
  /** What Catalogue of Life resolved it to, tried against GBIF first. */
  acceptedName?: string | null;
}

/**
 * Why the GBIF layer is missing.
 *
 * "No occurrences" and "GBIF has never heard of this name" are different
 * facts, and only one of them is about the species.
 */
function gbifEmptyMessage(gbif: GbifTaxonResult): string {
  switch (gbif.status) {
    case "unmatched":
      return "This name was not found in the GBIF taxonomic backbone, so no GBIF occurrences are shown.";
    case "error":
      return "GBIF could not be reached, so no GBIF occurrences are shown.";
    default:
      return "GBIF holds no georeferenced occurrences for this species.";
  }
}

const MARKER_LABELS: Record<MarkerKind, string> = {
  valid: "coordinate matches locality",
  flagged: "coordinate flagged",
  unvalidated: "not validated",
};

const numberFormat = new Intl.NumberFormat();

function Swatch({ color }: { color: string }) {
  return (
    <span
      aria-hidden
      className="inline-block w-2.5 h-2.5 rounded-full ring-1 ring-deep-mocha-900 dark:ring-white shrink-0"
      style={{ backgroundColor: color }}
    />
  );
}

function SpeciesDistribution({
  recordedName,
  acceptedName,
}: SpeciesDistributionProps) {
  const [specimens, setSpecimens] = useState<SpeciesCoordinates | null>(null);
  const [gbif, setGbif] = useState<GbifTaxonResult>({ status: "ok" });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;

    const load = async () => {
      setLoading(true);
      // Independent sources: either can fail without taking the other down.
      const [ours, theirs] = await Promise.all([
        fetchSpeciesCoordinates(recordedName.trim()),
        fetchGbifTaxon(recordedName.trim(), acceptedName),
      ]);
      if (ignore) return;
      setSpecimens(ours);
      setGbif(theirs);
      setLoading(false);
    };

    void load();
    return () => {
      ignore = true;
    };
  }, [recordedName, acceptedName]);

  const points = useMemo(() => specimens?.points ?? [], [specimens]);

  const kinds = useMemo(() => {
    const counts: Record<MarkerKind, number> = {
      valid: 0,
      flagged: 0,
      unvalidated: 0,
    };
    for (const point of points) counts[markerKind(point.validationStatus)]++;
    return counts;
  }, [points]);

  const hasGbif = gbif.status === "ok" && !!gbif.taxonKey && gbif.count !== 0;

  if (loading) {
    return <DistributionMapSkeleton msg="Fetching occurrence data" />;
  }

  return (
    // The same card as the classification above it: gradient header band over
    // a translucent body. The two sit stacked in the one narrow column, so
    // giving the map its own chrome made the column read as two unrelated
    // things.
    <div className="bg-linear-to-r from-white/50 to-white/30 dark:from-pacific-blue-900/30 dark:to-deep-mocha-800/50 rounded-xl backdrop-blur-lg">
      <div className="bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-t-xl">
        <h2 className="text-2xl font-semibold">Distribution Map</h2>
      </div>
      <div>
        {/* The legend is the info line: what each mark is and how many
            there are, in one place above the map. */}
        <div className="text-xs px-4 py-3 space-y-1.5 text-deep-mocha-700 dark:text-deep-mocha-300">
          {specimens === null ? (
            <p>LepiVerse specimen records could not be loaded.</p>
          ) : points.length === 0 ? (
            <p>No georeferenced LepiVerse specimen records for this species.</p>
          ) : (
            <div>
              <p className="font-medium text-deep-mocha-900 dark:text-deep-mocha-100">
                {numberFormat.format(specimens.total)} LepiVerse specimen{" "}
                {specimens.total === 1 ? "record" : "records"}
                {specimens.truncated &&
                  ` (${numberFormat.format(points.length)} shown)`}
              </p>
              <ul className="flex flex-wrap gap-x-3 gap-y-1 mt-1">
                {(Object.keys(kinds) as MarkerKind[])
                  .filter((kind) => kinds[kind] > 0)
                  .map((kind) => (
                    <li key={kind} className="flex items-center gap-1.5">
                      <Swatch color={MARKER_COLORS[kind]} />
                      {numberFormat.format(kinds[kind])} {MARKER_LABELS[kind]}
                    </li>
                  ))}
              </ul>
            </div>
          )}
          {hasGbif ? (
            <p className="flex items-center gap-1.5">
              <span
                aria-hidden
                className="inline-block w-6 h-2.5 rounded-sm shrink-0"
                style={{
                  background:
                    "linear-gradient(to right, #f6005a, #b4006c, #71005e)",
                }}
              />
              <span>
                GBIF occurrence density
                {typeof gbif.count === "number" &&
                  ` (${numberFormat.format(gbif.count)} records)`}
                {" · "}
                <a
                  href={`https://www.gbif.org/species/${gbif.taxonKey}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
                >
                  View on GBIF
                </a>
              </span>
            </p>
          ) : (
            <p>{gbifEmptyMessage(gbif)}</p>
          )}
        </div>
        <SpeciesMap
          points={points}
          gbifTaxonKey={hasGbif ? gbif.taxonKey : null}
        />
      </div>
    </div>
  );
}

export default SpeciesDistribution;
