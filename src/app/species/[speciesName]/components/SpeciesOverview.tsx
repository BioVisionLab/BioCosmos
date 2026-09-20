"use client";
import React, { useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { SpeciesImageGallery } from "./ImageGallery";
import { SpeciesDescription } from "./TaxonSummary";
import { SpeciesClassification } from "./TaxonClassification";
import ImageMetadata from "./ImageMetadata";
import { TaxonomyData } from "@/lib/speciesData";
import VisuallySimilarSpecies from "./SimilarSpecies";
import { LepTraits } from "@/lib/leptraits";
import { NoData } from "@/components/NoData";
import { useInView } from "@/lib/useInView";

const SpeciesDistribution = dynamic(
  () => import("@/app/species/[speciesName]/components/SpeciesMap"),
  {
    ssr: false,
    loading: () => (
      <div className="aspect-video bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-xl flex items-center justify-center">
        <NoData text="Loading map..." />
      </div>
    ),
  },
);

interface SpeciesOverviewProps {
  taxonomy: TaxonomyData | null;
  traits: LepTraits | null;
  /**
   * The name this page was opened under, as it appears in the occurrence
   * data.
   *
   * Every image, specimen and similarity endpoint keys on
   * `image_meta.species`, so lookups have to use this rather than
   * `taxonomy.species`: Catalogue of Life resolves a recorded name to its
   * accepted one, and for a taxon that has since been synonymized the two
   * differ. Querying by the accepted name would return an empty gallery for
   * exactly those species.
   */
  speciesSlug?: string;
}

export function SpeciesOverview({
  taxonomy,
  traits,
  speciesSlug,
}: SpeciesOverviewProps) {
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
  const [prevImageIds, setPrevImageIds] = useState<string[]>([]);
  const [nextImageIds, setNextImageIds] = useState<string[]>([]);
  const { ref: mapRef, inView: mapInView } = useInView<HTMLDivElement>();

  // Declared above the early return below: taxonomy flips from null to
  // populated in place, so every hook must run on both renders.
  const handleSelectionChange = useCallback(
    (payload: {
      imageId: string | null;
      items: string[];
      selectedIndex: number;
    }) => {
      setSelectedImageId(payload.imageId ?? null);
      setPrevImageIds(
        payload.items && payload.selectedIndex > 0
          ? payload.items.slice(
              Math.max(0, payload.selectedIndex - 2),
              payload.selectedIndex,
            )
          : [],
      );
      setNextImageIds(
        payload.items && payload.selectedIndex < payload.items.length - 1
          ? payload.items.slice(
              payload.selectedIndex + 1,
              payload.selectedIndex + 3,
            )
          : [],
      );
    },
    [],
  );

  // A null taxonomy means the name did not resolve against Catalogue of Life,
  // not that the page is still loading — page.tsx owns the loading and
  // not-found states. Everything here except the classification panel comes
  // from the occurrence data, so the page renders either way and
  // SpeciesClassification shows its own empty state.
  //
  // Data lookups go through the recorded name; only prose and headings use
  // the accepted one.
  const lookupName = speciesSlug ?? taxonomy?.species ?? "";
  const displayName = taxonomy?.species || lookupName.replace(/_/g, " ");

  return (
    <div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <SpeciesImageGallery
            speciesName={lookupName}
            onSelectionChange={handleSelectionChange}
          />

          <div className="mt-4">
            <ImageMetadata
              speciesName={lookupName}
              imageId={selectedImageId}
              prevImageIds={prevImageIds}
              nextImageIds={nextImageIds}
            />
          </div>

          <SpeciesDescription
            traits={traits}
            species={displayName}
          />
        </div>

        {/* Right Column: Details */}
        <div className="lg:col-span-1 space-y-5">
          <SpeciesClassification taxonomyData={taxonomy} />

          {/* The map pulls 200 GBIF occurrences plus the MapLibre bundle, so it
              only mounts once the reader scrolls near it. */}
          <div ref={mapRef}>
            {mapInView ? (
              <SpeciesDistribution speciesName={lookupName} />
            ) : (
              <div className="aspect-video bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-xl" />
            )}
          </div>
        </div>
      </div>
      <div className="mt-6">
        <VisuallySimilarSpecies species={lookupName} />
      </div>
    </div>
  );
}
