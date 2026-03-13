"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import {
  fetchImgById,
  fetchSpeciesImageIds,
  fetchThumbnailById,
} from "@/lib/images";
import { cleanSpeciesName } from "@/lib/names";
import Link from "next/link";
import { ImageLoading } from "@/components/Loadings";
import { MlResultItems } from "@/lib/ml_search";

// Image size matching the backend resizing
const IMAGE_SIZE = 128;
// Compute match percent from a 0..1 distance value using the app's scaling formula
function computeMatchPercent(distance: number) {
  return Math.round(50.0 + (distance - 0.501) * (50.0 / (0.999 - 0.501)));
}
// Reusable component for displaying a species card (similar to GenusSpeciesClient)
function MLSearchResultCard({ data }: { data: MlResultItems }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const fetchImage = async () => {
      try {
        const response = await fetchThumbnailById(data.imgId);
        setImageUrl(response);
      } catch (error) {
        console.error("Error fetching similar species image:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchImage();
  }, [data.imgId]);

  const speciesName = cleanSpeciesName(data.species);

  // Format similarity (0..1) as a percentage for display (now uses `score`)
  const matchPercent = computeMatchPercent(data.score);

  // Return Tailwind classes for a colored pill (bg + text) with dark-mode variants
  const getMatchPillClass = (pct: number) => {
    // base pill styling: small rounded pill with tight padding and monospace-ish size
    const base =
      "inline-block px-2 py-0.5 rounded-full text-[11px] font-medium";
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
    <div className="bg-gray-200 dark:bg-gray-700 rounded-2xl p-4 flex flex-col items-center justify-center text-center w-[160px] min-h-[200px]">
      {loading ? (
        <ImageLoading size={IMAGE_SIZE} />
      ) : (
        <Link
          href={`/species/${data.species}`}
          className="flex flex-col items-center justify-between h-full w-full gap-2"
        >
          <div className="flex flex-1 items-center justify-center w-full">
            <Image
              src={imageUrl || `/api/image/${data.imgId}`}
              alt={`Image of ${data.species}`}
              width={IMAGE_SIZE}
              height={IMAGE_SIZE}
              className="mx-auto object-contain"
            />
          </div>

          <h2 className="text-sm truncate text-center text-gray-400 italic w-full">
            {speciesName}
          </h2>

          <p className="text-xs text-gray-500 w-full">
            <span className={getMatchPillClass(matchPercent)}>
              Match: {matchPercent}%
            </span>
          </p>
        </Link>
      )}
    </div>
  );
}

function TopResultCard({ data }: { data: MlResultItems }) {
  const [speciesImageUrl, setSpeciesImageUrl] = useState<string | null>(null);
  const [otherImageUrls, setOtherImageUrl] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let mounted = true;
    const fetchImages = async () => {
      setLoading(true);
      try {
        const speciesImage = await fetchImgById(data.imgId);
        if (!mounted) return;
        setSpeciesImageUrl(speciesImage);
        const imageIds = await fetchSpeciesImageIds(data.species, 5);
        if (imageIds.length > 0) {
          const otherImages = await Promise.all(
            imageIds.map((id) => fetchThumbnailById(id)),
          );
          if (!mounted) return;
          setOtherImageUrl(otherImages);
        }
      } catch (error) {
        console.error("Error fetching images for TopResultCard:", error);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    fetchImages();
    return () => {
      mounted = false;
    };
  }, [data.species, data.imgId]);

  if (!data) return null;

  const matchPercent = computeMatchPercent(data.score);

  const getMatchPillClass = (pct: number) => {
    const base =
      "inline-block px-2 py-0.5 rounded-full text-[13px] font-medium";
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
    <div className="rounded-2xl shadow-md w-fit bg-gradient-to-br dark:from-teal-700/50 dark:to-gray-800/50 min-w-4xl">
      <div className="bg-gradient-to-br from-teal-500/20 to-emerald-300/10 p-4 rounded-t-2xl flex items-center gap-3">
        <h2 className="text-lg font-semibold p-1">Top Result</h2>
        <span className={getMatchPillClass(matchPercent)}>
          Match: {matchPercent}%
        </span>
      </div>

      <div className="p-4">
        <Link href={`/species/${data.species}`}>
          <h2 className="text-2xl font-semibold mb-2 italic text-start text-gray-300 dark:text-gray-300 mt-4">
            {cleanSpeciesName(data.species)}
          </h2>
        </Link>

        {loading ? (
          <ImageLoading size={160} />
        ) : (
          <div className="flex gap-12 items-start m-4 p-3">
            <div className="flex flex-col items-start">
              {speciesImageUrl && (
                <Image
                  src={speciesImageUrl}
                  alt={`Matched image of ${data.species}`}
                  width={260}
                  height={260}
                  className="rounded-lg object-contain"
                />
              )}
            </div>

            <div className="flex flex-col items-start">
              <h3 className="text-sm mb-2 text-gray-400">Other forms:</h3>
              {otherImageUrls && (
                <div className="gap-2 overflow-auto flex">
                  {otherImageUrls.map((url, index) => (
                    <div
                      key={index}
                      className="p-3 border border-gray-500 rounded-lg bg-gray-100 dark:bg-gray-700"
                    >
                      <Image
                        src={url}
                        alt={`Other image ${index + 1} of ${data.species}`}
                        width={70}
                        height={70}
                        className="rounded-lg object-contain"
                      />
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-4">
                <Link
                  href={`/species/${data.species}`}
                  className="mb-2 inline-block rounded-lg bg-gradient-to-br from-emerald-500/50 to-teal-700/50 w-fit px-4 py-2 hover:bg-teal-600/70 transition text-gray-100"
                >
                  Show species page →
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export { TopResultCard, MLSearchResultCard };
