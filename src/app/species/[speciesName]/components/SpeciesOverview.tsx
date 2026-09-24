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
import { useInView } from "@/lib/useInView";
import { DistributionMapSkeleton } from "./DistributionMapSkeleton";

const SpeciesDistribution = dynamic(
  () => import("@/app/species/[speciesName]/components/SpeciesMap"),
  {
    ssr: false,
    loading: () => <DistributionMapSkeleton msg="Loading map" />,
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
  /**
   * Switch the page to the Specimens tab. The overview gallery shows only a
   * first page of images, so the note under it needs a way to send a reader
   * to the full set rather than just naming the tab.
   */
  onViewSpecimens?: () => void;
}

export function SpeciesOverview({
  taxonomy,
  traits,
  speciesSlug,
  onViewSpecimens,
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

          {/* The gallery above holds one page of images; the Specimens tab
              holds all of them. Saying so here is the only cue a reader
              gets. */}
          <p className="mt-2 text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
            {onViewSpecimens ? (
              <button
                type="button"
                onClick={onViewSpecimens}
                className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
              >
                Open the Specimens tab
              </button>
            ) : (
              <span>Open the Specimens tab</span>
            )}{" "}
            to browse every image of this species.
          </p>

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

          {/* The map pulls our specimen coordinates, the GBIF density tiles
              and the MapLibre bundle, so it only mounts once the reader
              scrolls near it.

              GBIF is the exception to the recorded-name rule above: it is an
              external backbone rather than our gallery, so it gets both names
              and matches whichever it knows. */}
          <div ref={mapRef}>
            {mapInView ? (
              <SpeciesDistribution
                recordedName={lookupName}
                acceptedName={taxonomy?.acceptedName ?? taxonomy?.species ?? null}
              />
            ) : (
              <DistributionMapSkeleton />
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
