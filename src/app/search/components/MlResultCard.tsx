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

  // Format similarity (0..1) as a percentage for display
  const matchPercent = Math.round(
    50.0 + (data.distance - 0.501) * (50.0 / (0.999 - 0.501))
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
        <Link href={`/species/${data.species}`}>
          <Image
            src={imageUrl || `/api/image/${data.imgId}`}
            alt={`Image of ${data.species}`}
            width={IMAGE_SIZE}
            height={IMAGE_SIZE}
            className="mx-auto object-contain"
          />

          <h2 className="text-sm truncate text-center text-gray-400 italic mt-2">
            {speciesName}
          </h2>
          <p className="text-xs text-gray-500">
            <span className={getMatchPillClass(matchPercent)}>Match: {matchPercent}%</span>
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
    const fetchImages = async () => {
      try {
        const speciesImage = await fetchImgById(data.imgId);
        setSpeciesImageUrl(speciesImage);
        const imageIds = await fetchSpeciesImageIds(data.species, 5);
        if (imageIds.length > 0) {
          const otherImages = await Promise.all(
            imageIds.map((id) => fetchThumbnailById(id))
          );
          setOtherImageUrl(otherImages);
        }
      } catch (error) {
        console.error("Error fetching images for TopResultCard:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchImages();
  }, [data.species, data.imgId]);

  if (!data) {
    return null;
  }

  return (
    <div className="rounded-2xl shadow-md w-fit bg-gradient-to-br dark:from-teal-700/50 dark:to-gray-800/50">
      <div className="bg-gradient-to-br from-teal-500/20 to-emerald-300/10 p-4 rounded-t-2xl">
        <h2 className="text-lg font-semibold">Top Result</h2>
      </div>
      <Link href={`/species/${data.species}`}>
        <h2 className="text-2xl font-semibold mb-2 italic text-start text-gray-300 dark:text-gray-300 mt-4 m-4">
          {cleanSpeciesName(data.species)}
        </h2>
        {loading ? (
          <ImageLoading size={160} />
        ) : (
          <div className="flex gap-12 items-center m-4">
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
            <div className="items-start">
              <h3 className="text-sm mb-2 text-gray-400 ">Other forms</h3>
              {otherImageUrls && (
                <div className="gap-2 overflow-auto flex">
                  {otherImageUrls.map((url, index) => (
                    <div
                      key={index}
                      className="p-2 border border-gray-500 rounded-lg bg-gray-100 dark:bg-gray-700"
                    >
                      <Image
                        key={index}
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
            </div>
          </div>
        )}
      </Link>
    </div>
  );
}

export { TopResultCard, MLSearchResultCard };
