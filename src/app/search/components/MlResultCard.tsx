"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import {
  fetchImgById,
  fetchSpeciesImageIds,
  fetchThumbnailById,
  imageUrlById,
} from "@/lib/images";
import { cleanSpeciesName, toBinomialName } from "@/lib/names";
import { speciesPageHref } from "@/lib/taxonSlug";
import Link from "next/link";
import { ImageLoading } from "@/components/Loadings";
import NoImage from "@/components/NoImage";
import { SemanticFunctionBadges } from "@/components/SemanticSearchFunctions";
import { MlResultItems } from "@/lib/ml_search";

// Image size matching the backend resizing
const IMAGE_SIZE = 128;

/**
 * Wrap children in a link to the species page, when there is one to link to.
 *
 * The backend names the page (`speciesKey`) and leaves it null for a record
 * with none, such as one identified only to genus. Those results are still
 * worth showing — they are real images that matched — so the card renders,
 * it just does not pretend to lead somewhere.
 */
function MaybeSpeciesLink({
  speciesKey,
  className,
  children,
}: {
  speciesKey?: string | null;
  className?: string;
  children: React.ReactNode;
}) {
  const href = speciesPageHref(speciesKey);
  if (!href) {
    return <div className={className}>{children}</div>;
  }
  return (
    <Link href={href} className={className}>
      {children}
    </Link>
  );
}

/** The name a card shows: the page it leads to, else the recorded name. */
function resultName(data: MlResultItems): string {
  return toBinomialName(cleanSpeciesName(data.speciesKey || data.species));
}

function computeMatchPercent(score: number) {
  return Math.max(0, Math.min(100, Math.round(score * 100)));
}

// Compute match percent from a cosine distance.
//
// Every vector search runs with `distance_type("cosine")`, whose range is
// 0..2: identical, orthogonal at 1, opposed at 2. Halving is what maps that
// onto a percentage. Treating the range as 0..1 clamped every text query to
// "Match: 0%" — text and image embeddings sit far enough apart that a good
// colour match still scores around 1.38.
function computeDistancePercent(distance: number) {
  const similarity = 1 - distance / 2;
  return Math.max(0, Math.min(100, Math.round(similarity * 100)));
}

function MLSearchResultCard({ data, toolNames }: { data: MlResultItems; toolNames?: string[] }) {
  // Building the URL needs no I/O. Resolving it synchronously lets a grid
  // restored from cache paint straight from the browser's immutable image
  // cache instead of flashing a spinner per card.
  const imageUrl = imageUrlById(data.imgId, "thumbnail");
  const [imageFailed, setImageFailed] = useState(false);

  const speciesName = resultName(data);

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
    <div className={`bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-2xl p-4 flex flex-col items-center justify-center text-center min-h-[200px] ${toolNames ? "w-full min-w-0" : "w-[160px]"}`}>
      <MaybeSpeciesLink
          speciesKey={data.speciesKey}
          className="flex flex-col items-center justify-between h-full w-full gap-2"
        >
          <div className="flex flex-1 items-center justify-center w-full">
            <div className="relative aspect-square w-full max-w-32">
              {imageFailed ? (
                <NoImage />
              ) : (
                <Image
                  src={imageUrl}
                  alt={`Image of ${data.species}`}
                  fill
                  sizes={`${IMAGE_SIZE}px`}
                  className="object-contain"
                  onError={() => setImageFailed(true)}
                  unoptimized
                />
              )}
            </div>
          </div>

          <h2 className={`text-sm text-center italic w-full ${toolNames ? "break-words text-deep-mocha-800 dark:text-deep-mocha-100" : "truncate text-deep-mocha-400"}`}>
            {speciesName}
          </h2>

          <div className="flex flex-col gap-1 items-center w-full">
            {toolNames && <SemanticFunctionBadges toolNames={toolNames} />}
            {!toolNames && data.score !== undefined && (
              <span
                className={getMatchPillClass(computeMatchPercent(data.score))}
              >
                Match: {computeMatchPercent(data.score)}%
              </span>
            )}
            {!toolNames && data.distance !== undefined && (
              <span
                className={getMatchPillClass(
                  computeDistancePercent(data.distance),
                )}
              >
                Match: {computeDistancePercent(data.distance)}%
              </span>
            )}
          </div>
        </MaybeSpeciesLink>
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
        const imageIds = await fetchSpeciesImageIds(
          data.speciesKey || data.species,
          5,
        );
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
  }, [data.species, data.speciesKey, data.imgId]);

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

  const pageHref = speciesPageHref(data.speciesKey);

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
        <MaybeSpeciesLink speciesKey={data.speciesKey}>
          <h2 className="text-2xl font-semibold mb-2 italic text-start text-deep-mocha-300 dark:text-deep-mocha-300 mt-4">
            {resultName(data)}
          </h2>
        </MaybeSpeciesLink>

        {loading ? (
          <ImageLoading size={160} />
        ) : (
          <div className="flex gap-12 items-start m-4 p-3">
            <div className="flex flex-col items-start">
              {speciesImageUrl && (
                <div className="relative aspect-square w-[260px] max-w-full">
                  <Image
                    src={speciesImageUrl}
                    alt={`Matched image of ${data.species}`}
                    fill
                    sizes="260px"
                    className="rounded-lg object-contain"
                    unoptimized
                  />
                </div>
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
                      <div className="relative h-[70px] w-[70px]">
                        <Image
                          src={url}
                          alt={`Other image ${index + 1} of ${data.species}`}
                          fill
                          sizes="70px"
                          className="rounded-lg object-contain"
                          unoptimized
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Omitted rather than disabled for a record with no species
                  page to show. */}
              {pageHref ? (
                <div className="mt-4">
                  <Link
                    href={pageHref}
                    className="mb-2 inline-block rounded-lg bg-gradient-to-br from-hunter-green-500/50 to-pacific-blue-700/50 w-fit px-4 py-2 hover:bg-pacific-blue-600/70 transition text-deep-mocha-100"
                  >
                    Show species page →
                  </Link>
                </div>
              ) : null}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export { TopResultCard, MLSearchResultCard };
