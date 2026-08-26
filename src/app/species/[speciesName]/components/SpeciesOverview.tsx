"use client";
import React, { useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { SpeciesImageGallery } from "./ImageGallery";
import { SpeciesDescription } from "./TaxonSummary";
import { SpeciesClassification } from "./TaxonClassification";
import ImageMetadata from "./ImageMetadata";
import { RedListStatus } from "./IucnRedlist";
import { TaxonomyData } from "@/lib/speciesData";
import VisuallySimilarSpecies from "./SimilarSpecies";
import { LepTraits } from "@/lib/leptraits";
import { NoData } from "@/components/NoData";
import { ImageLoading } from "@/components/Loadings";
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
}

export function SpeciesOverview({ taxonomy, traits }: SpeciesOverviewProps) {
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

  // The page shell renders before taxonomy resolves, so a null taxonomy here
  // means "still loading" — the genuine not-found case is handled upstream in
  // the species page itself.
  if (!taxonomy) {
    return (
      <div className="flex items-center justify-center py-16">
        <ImageLoading size={220} msg="Fetching species details" />
      </div>
    );
  }

  return (
    <div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <SpeciesImageGallery
            speciesName={taxonomy?.species ?? ""}
            onSelectionChange={handleSelectionChange}
          />

          <div className="mt-4">
            <ImageMetadata
              speciesName={taxonomy?.species ?? ""}
              imageId={selectedImageId}
              prevImageIds={prevImageIds}
              nextImageIds={nextImageIds}
            />
          </div>

          <SpeciesDescription
            traits={traits}
            species={taxonomy?.species ?? ""} // Use species from taxonomy or fallback to name
          />
        </div>

        {/* Right Column: Details */}
        <div className="lg:col-span-1 space-y-5">
          <SpeciesClassification taxonomyData={taxonomy} />

          <RedListStatus
            statusCode={taxonomy?.redlistCategory ?? "Unknown"}
            horizontal
          />

          {/* The map pulls 200 GBIF occurrences plus the Leaflet bundle, so it
              only mounts once the reader scrolls near it. */}
          <div ref={mapRef}>
            {mapInView ? (
              <SpeciesDistribution speciesName={taxonomy?.species ?? ""} />
            ) : (
              <div className="aspect-video bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-xl" />
            )}
          </div>
        </div>
      </div>
      <div className="mt-6">
        <VisuallySimilarSpecies species={taxonomy?.species ?? ""} />
      </div>
    </div>
  );
}
