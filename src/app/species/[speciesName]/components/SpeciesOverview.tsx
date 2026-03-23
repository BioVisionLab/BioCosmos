"use client";
import Link from "next/link";
import React, { useEffect, useState, useCallback } from "react";
import { ImageLoading } from "@/components/Loadings";
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

const SpeciesDistribution = dynamic(
  () => import("@/app/species/[speciesName]/components/SpeciesMap"),
  {
    ssr: false,
    loading: () => (
      <div className="aspect-video bg-gray-200 dark:bg-gray-700 rounded flex items-center justify-center">
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
  if (!taxonomy) {
    return (
      <section className="container mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold mb-6">Species Not Found</h1>
        <p>The requested species could not be found.</p>
        <Link
          href="/"
          className="text-blue-600 hover:underline mt-4 inline-block"
        >
          Return to homepage
        </Link>
      </section>
    );
  }
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
  const [prevImageIds, setPrevImageIds] = useState<string[]>([]);
  const [nextImageIds, setNextImageIds] = useState<string[]>([]);

  return (
    <div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <SpeciesImageGallery
            speciesName={taxonomy?.species ?? ""}
            onSelectionChange={useCallback((payload: { imageId: string | null; items: string[]; selectedIndex: number }) => {
              setSelectedImageId(payload.imageId ?? null);
              setPrevImageIds(
                payload.items && payload.selectedIndex > 0
                  ? payload.items.slice(Math.max(0, payload.selectedIndex - 2), payload.selectedIndex)
                  : []
              );
              setNextImageIds(
                payload.items && payload.selectedIndex < payload.items.length - 1
                  ? payload.items.slice(payload.selectedIndex + 1, payload.selectedIndex + 3)
                  : []
              );
            }, [setSelectedImageId, setPrevImageIds, setNextImageIds])}
          />

          <div className="mt-4">
            <ImageMetadata speciesName={taxonomy?.species ?? ""} imageId={selectedImageId} prevImageIds={prevImageIds} nextImageIds={nextImageIds} />
          </div>

          <SpeciesDescription
            traits={traits}
            species={taxonomy?.species ?? ""} // Use species from taxonomy or fallback to name
          />
        </div>

        {/* Right Column: Details */}
        <div className="lg:col-span-1 space-y-6">
          <SpeciesClassification taxonomyData={taxonomy} />

          <div className="bg-gray-100 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl flex items-center w-full">
            <RedListStatus statusCode={taxonomy?.redlistCategory ?? "Unknown"} horizontal />
          </div>

          <SpeciesDistribution speciesName={taxonomy?.species ?? ""} />
        </div>
      </div>
      <div className="mt-6">
        <VisuallySimilarSpecies species={taxonomy?.species ?? ""} />
      </div>
    </div>
  );
}
