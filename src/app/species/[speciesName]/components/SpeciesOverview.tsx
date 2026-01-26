"use client";
import Link from "next/link";
import React, { useEffect, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import dynamic from "next/dynamic";
import { SpeciesImageGallery } from "./ImageGallery";
import { SpeciesDescription } from "./TaxonSummary";
import { SpeciesClassification } from "./TaxonClassification";
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
  }
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

  return (
    <div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <SpeciesImageGallery speciesName={taxonomy?.species ?? ""} />

          <SpeciesDescription
            traits={traits}
            species={taxonomy?.species ?? ""} // Use species from taxonomy or fallback to name
          />
        </div>

        {/* Right Column: Details */}
        <div className="lg:col-span-1 space-y-6">
          <SpeciesClassification taxonomyData={taxonomy} />
          <RedListStatus statusCode={taxonomy?.redlistCategory ?? "Unknown"} />
          <SpeciesDistribution speciesName={taxonomy?.species ?? ""} />
        </div>
      </div>
      <div className="mt-6">
<<<<<<< HEAD
        {/* Render placeholders immediately; mount the similar-species gallery after first paint */}
        <DeferredSimilar species={taxonomy?.species ?? ""} meta={similarSpecies} />
      </div>
    </div>
  );
}

function DeferredSimilar({ species, meta }: { species: string; meta: SimilarSpeciesMeta[] }) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    // Wait until the full window load event fires so the rest of the page
    // (images, maps, etc.) has completed loading before mounting the
    // similar-species component and starting its thumbnail requests.
    let mounted = true;
    const onLoad = () => {
      if (!mounted) return;
      setShow(true);
    };

    try {
      if (typeof window !== "undefined") {
        if (document.readyState === "complete") {
          // load already fired
          onLoad();
        } else {
          window.addEventListener("load", onLoad);
        }
      }
    } catch (e) {
      // If anything goes wrong, fall back to immediate mount
      onLoad();
    }

    return () => {
      mounted = false;
      try {
        if (typeof window !== "undefined") window.removeEventListener("load", onLoad);
      } catch (e) {
        /* ignore */
      }
    };
  }, []);

  if (!meta || meta.length === 0) return null;

  return show ? <VisuallySimilarSpecies species={species} meta={meta} /> : (
    <div className="mt-4 border border-gray-300 dark:border-gray-600 rounded-xl bg-gray-200/50 dark:bg-gray-800/50 backdrop-blur p-4">
      <div className="border-b border-gray-300 dark:border-gray-600 p-4">
        <h2 className="text-2xl font-semibold">Visually Similar Species</h2>
        <p className={`text-sm text-gray-500 dark:text-gray-400`}>Loading similar species…</p>
      </div>
      <div className="p-4 mt-2">
        <div className="overflow-x-auto rounded-xl flex flex-row gap-4">
          {Array.from({ length: Math.min(6, meta.length) }).map((_, i) => (
            <div key={`ph-${i}`} className="w-[128px] h-[128px] bg-gray-300 dark:bg-gray-700 rounded-lg flex items-center justify-center">
              <ImageLoading size={128} />
            </div>
          ))}
        </div>
=======
        <VisuallySimilarSpecies species={taxonomy?.species ?? ""} />
>>>>>>> api-redesign
      </div>
    </div>
  );
}
