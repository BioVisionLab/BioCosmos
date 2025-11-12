"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { fetchThumbnailById } from "@/lib/images";
import { cleanSpeciesName } from "@/lib/names";
import Link from "next/link";
import { ImageLoading } from "@/components/Loadings";
import { SemanticResultItem } from "@/lib/ml_search";

// Image size matching the backend resizing
const IMAGE_SIZE = 128;
// Reusable component for displaying a species card (similar to GenusSpeciesClient)
function SpeciesSearchResultCard({ species }: { species: SemanticResultItem }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const fetchImage = async () => {
      try {
        const response = await fetchThumbnailById(species.imgId);
        setImageUrl(response);
      } catch (error) {
        console.error("Error fetching similar species image:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchImage();
  }, [species.imgId]);

  const speciesName = cleanSpeciesName(species.species);
  // Format similarity (0..1) as a percentage for display
  const matchPercent = Math.round(
    50.0 + (species.distance - 0.501) * (50.0 / (0.999 - 0.501))
  );

  // Return Tailwind classes for a colored pill (bg + text) with dark-mode variants
  const getMatchPillClass = (pct: number) => {
    // base pill styling: small rounded pill with tight padding and monospace-ish size
    const base = "inline-block px-2 py-0.5 rounded-full text-[11px] font-medium";
    if (pct < 65)
      return `${base} bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200`;
    if (pct < 70)
      return `${base} bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200`;
    if (pct < 75)
      return `${base} bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200`;
    if (pct < 80)
      return `${base} bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200`;
    return `${base} bg-emerald-200 text-emerald-900 dark:bg-emerald-800 dark:text-emerald-100`;
  };

  return (
    <div className="bg-gray-100 dark:bg-gray-700 rounded-2xl p-2 items-center justify-center text-center w-[160px]">
      {loading ? (
        <ImageLoading size={IMAGE_SIZE} />
      ) : (
        <Link href={`/species/${species.species}`}>
          <Image
            src={imageUrl || `/api/image/${species.imgId}`}
            alt={`Image of ${species.species}`}
            width={IMAGE_SIZE}
            height={IMAGE_SIZE}
            className="mx-auto object-contain"
          />

          <h2 className="text-sm truncate text-center text-gray-400 italic mt-2">
            {speciesName}
          </h2>
          <p className="text-xs mt-1">
            <span className={getMatchPillClass(matchPercent)}>Match: {matchPercent}%</span>
          </p>
        </Link>
      )}
    </div>
  );
}

export default SpeciesSearchResultCard;
