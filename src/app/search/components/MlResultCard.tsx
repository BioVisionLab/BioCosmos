"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import {
  fetchImgById,
  fetchSpeciesImageIds,
  fetchThumbnailById,
} from "@/lib/images";
import { cleanSpeciesName, speciesUrlFromName } from "@/lib/names";
import Link from "next/link";
import { ImageLoading } from "@/components/Loadings";
import { MlResultItems } from "@/lib/ml_search";

// Image size matching the backend resizing
const IMAGE_SIZE = 128;

// Compute match percent from a 0..1 normalized score provided by the backend agent
// Use for semantic search that returns normalized scores.
function computeMatchPercent(score: number) {
  return Math.max(0, Math.min(100, Math.round(score * 100)));
}

// Compute match percent inversely from a raw Euclidean/Cosine distance (0.0 = perfect match, 1.0+ = irrelevant)
// Use for image search that returns cosine distances.
function computeDistancePercent(distance: number) {
  const similarity = Math.max(0, 1 - distance);
  return Math.max(0, Math.min(100, Math.round(similarity * 100)));
}

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

  const getMatchPillClass = (pct: number) => {
    const base =
      "inline-block px-2 py-0.5 rounded-full text-[11px] font-medium";
    if (pct < 65)
      return `${base} bg-burnt-peach-100 text-burnt-peach-800 dark:bg-burnt-peach-900 dark:text-burnt-peach-200`;
    if (pct < 70)
      return `${base} bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200`;
    if (pct < 75)
      return `${base} bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200`;
    if (pct < 80)
      return `${base} bg-hunter-green-100 text-hunter-green-800 dark:bg-hunter-green-900 dark:text-hunter-green-200`;
    return `${base} bg-hunter-green-200 text-hunter-green-900 dark:bg-hunter-green-800 dark:text-hunter-green-100`;
  };

  return (
    <div className="bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-2xl p-4 flex flex-col items-center justify-center text-center w-[160px] min-h-[200px]">
      {loading ? (
        <ImageLoading size={IMAGE_SIZE} />
      ) : (
        <Link
          href={`/species/${speciesUrlFromName(data.species)}`}
          className="flex flex-col items-center justify-between h-full w-full gap-2"
        >
          <div className="flex flex-1 items-center justify-center w-full">
            <Image
              src={imageUrl || `/api/image/${data.imgId}`}
              alt={`Image of ${data.species}`}
              width={IMAGE_SIZE}
              height={IMAGE_SIZE}
              className="mx-auto object-contain"
              unoptimized
            />
          </div>

          <h2 className="text-sm truncate text-center text-deep-mocha-400 italic w-full">
            {speciesName}
          </h2>

          <div className="flex flex-col gap-1 items-center w-full">
            {data.score !== undefined && (
              <span
                className={getMatchPillClass(computeMatchPercent(data.score))}
              >
                Match: {computeMatchPercent(data.score)}%
              </span>
            )}
            {data.distance !== undefined && (
              <span
                className={getMatchPillClass(
                  computeDistancePercent(data.distance),
                )}
              >
                Match: {computeDistancePercent(data.distance)}%
              </span>
            )}
          </div>
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

  const getMatchPillClass = (pct: number) => {
    const base =
      "inline-block px-2 py-0.5 rounded-full text-[13px] font-medium";
    if (pct < 65)
      return `${base} bg-burnt-peach-100 text-burnt-peach-800 dark:bg-burnt-peach-900 dark:text-burnt-peach-200`;
    if (pct < 70)
      return `${base} bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200`;
    if (pct < 75)
      return `${base} bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200`;
    if (pct < 80)
      return `${base} bg-hunter-green-100 text-hunter-green-800 dark:bg-hunter-green-900 dark:text-hunter-green-200`;
    return `${base} bg-hunter-green-200 text-hunter-green-900 dark:bg-hunter-green-800 dark:text-hunter-green-100`;
  };

  return (
    <div className="rounded-2xl shadow-md w-fit bg-gradient-to-br dark:from-pacific-blue-700/50 dark:to-deep-mocha-800/50 min-w-4xl">
      <div className="bg-gradient-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-t-2xl flex items-center gap-3">
        <h2 className="text-lg font-semibold p-1">Top Result</h2>
        {data.score !== undefined && (
          <span className={getMatchPillClass(computeMatchPercent(data.score))}>
            Match: {computeMatchPercent(data.score)}%
          </span>
        )}
        {data.distance !== undefined && (
          <span
            className={getMatchPillClass(computeDistancePercent(data.distance))}
          >
            Match: {computeDistancePercent(data.distance)}%
          </span>
        )}
      </div>

      <div className="p-4">
        <Link href={`/species/${speciesUrlFromName(data.species)}`}>
          <h2 className="text-2xl font-semibold mb-2 italic text-start text-deep-mocha-300 dark:text-deep-mocha-300 mt-4">
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
                  unoptimized
                />
              )}
            </div>

            <div className="flex flex-col items-start">
              <h3 className="text-sm mb-2 text-deep-mocha-400">Other forms:</h3>
              {otherImageUrls && (
                <div className="gap-2 overflow-auto flex">
                  {otherImageUrls.map((url, index) => (
                    <div
                      key={index}
                      className="p-3 border border-deep-mocha-500 rounded-lg bg-deep-mocha-100 dark:bg-deep-mocha-700"
                    >
                      <Image
                        src={url}
                        alt={`Other image ${index + 1} of ${data.species}`}
                        width={70}
                        height={70}
                        className="rounded-lg object-contain"
                        unoptimized
                      />
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-4">
                <Link
                  href={`/species/${speciesUrlFromName(data.species)}`}
                  className="mb-2 inline-block rounded-lg bg-gradient-to-br from-hunter-green-500/50 to-pacific-blue-700/50 w-fit px-4 py-2 hover:bg-pacific-blue-600/70 transition text-deep-mocha-100"
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
