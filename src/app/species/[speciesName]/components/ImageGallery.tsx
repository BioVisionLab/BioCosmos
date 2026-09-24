"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { ImageLoading } from "@/components/Loadings";
import NoImage from "@/components/NoImage";
import {
  fetchImgById,
  fetchThumbnailById,
  fetchSpeciesImageIds,
} from "@/lib/images";
import Image from "next/image";
import React, { useEffect, useState } from "react";

export function SpeciesImageGallery({
  speciesName,
  onSelectionChange,
}: {
  speciesName: string;
  onSelectionChange?: (payload: {
    imageId: string | null;
    items: string[];
    selectedIndex: number;
  }) => void;
}) {
  const [items, setItems] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

  useEffect(() => {
    if (!speciesName) {
      setItems([]);
      setSelectedIndex(0);
      setLoading(false);
      return;
    }

    let ignore = false; // React docs pattern for race conditions
    const run = async () => {
      setLoading(true);
      setSelectedIndex(0);
      setItems([]);

      try {
        // Dorsal views first, then ventral, so the gallery opens on the
        // upperside a reader expects.
        const ids = await fetchSpeciesImageIds(speciesName, 8, 0, "view");
        if (!ignore) setItems(ids);
        // notify initial selection (provide items and selectedIndex)
        if (!ignore && onSelectionChange)
          onSelectionChange({
            imageId: ids && ids.length ? ids[0] : null,
            items: ids,
            selectedIndex: 0,
          });
      } catch (e) {
        if (!ignore) setItems([]);
      } finally {
        if (!ignore) setLoading(false);
      }
    };

    run();
    return () => {
      ignore = true;
    };
  }, [speciesName]);

  const handleThumbnailClick = (index: number) => {
    setSelectedIndex(index);
  };

  // notify when selectedIndex changes
  useEffect(() => {
    if (onSelectionChange) {
      onSelectionChange({
        imageId: items && items[selectedIndex] ? items[selectedIndex] : null,
        items,
        selectedIndex,
      });
    }
  }, [selectedIndex, items, onSelectionChange]);

  return (
    <div
      className={`relative w-full overflow-hidden rounded-xl bg-deep-mocha-100 dark:bg-deep-mocha-900 ${
        loading
          ? "flex items-center justify-center border border-deep-mocha-200 dark:border-deep-mocha-700 min-h-[400px]"
          : ""
      }`}
    >
      {loading ? (
        <ImageLoading size={400} />
      ) : items.length === 0 ? (
        <div className="relative min-h-[400px] w-full">
          <NoImage />
        </div>
      ) : (
        <div className="flex flex-col gap-3 h-full">
          {/* add outer padding so thumbs have breathing room */}
          {/* Main image */}
          <div className="relative w-full min-h-[400px] flex-grow rounded-xl overflow-hidden border  border-deep-mocha-200 dark:border-deep-mocha-700">
            {/* Left/right circular nav buttons (scroll through the 8 images) */}
            <button
              aria-label="Previous image"
              onClick={() =>
                handleThumbnailClick(Math.max(0, selectedIndex - 1))
              }
              disabled={selectedIndex <= 0}
              className={`absolute left-3 top-1/2 -translate-y-1/2 z-20 rounded-full p-2 transition-colors ${
                selectedIndex <= 0
                  ? "text-deep-mocha-400 cursor-not-allowed bg-transparent"
                  : "text-white bg-pacific-blue-500 dark:bg-pacific-blue-800 hover:bg-pacific-blue-400 dark:hover:bg-pacific-blue-700 shadow-md"
              }`}
            >
              <ChevronLeft className="h-5 w-5" aria-hidden="true" />
            </button>

            <GalleryFullImage
              imageId={items[selectedIndex]}
              speciesName={speciesName}
            />

            <button
              aria-label="Next image"
              onClick={() =>
                handleThumbnailClick(
                  Math.min(items.length - 1, selectedIndex + 1),
                )
              }
              disabled={selectedIndex >= items.length - 1}
              className={`absolute right-3 top-1/2 -translate-y-1/2 z-20 rounded-full p-2 transition-colors ${
                selectedIndex >= items.length - 1
                  ? "text-deep-mocha-400 cursor-not-allowed bg-transparent"
                  : "text-white bg-pacific-blue-500 dark:bg-pacific-blue-800 hover:bg-pacific-blue-400 dark:hover:bg-pacific-blue-700 shadow-md"
              }`}
            >
              <ChevronRight className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>

          {/* Thumbnails (show up to 8 total images, keeping order) */}
          {items.length > 1 && (
            <div className="flex gap-3 overflow-x-auto">
              {/* increased gap and top padding */}
              {items.map((id, idx) => (
                <button
                  key={id}
                  type="button"
                  aria-label={`View image ${idx + 1} of ${speciesName}`}
                  title={`View image ${idx + 1} of ${speciesName}`}
                  onClick={() => handleThumbnailClick(idx)}
                  className={`relative w-24 h-24 flex-shrink-0 rounded-xl overflow-hidden border transition-all p-2 ${
                    idx === selectedIndex
                      ? "border-hunter-green-300"
                      : "border-deep-mocha-300 dark:border-deep-mocha-700 hover:border-pacific-blue-600"
                  }`}
                >
                  <GalleryThumbnail
                    imageId={id}
                    idx={idx}
                    speciesName={speciesName}
                  />
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function GalleryFullImage({
  imageId,
  speciesName,
}: {
  imageId: string;
  speciesName: string;
}) {
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // Keyed by URL so moving to the next image clears a previous failure.
  const [failedUrl, setFailedUrl] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const loadFullImage = async () => {
      try {
        const url = await fetchImgById(imageId);
        setImgUrl(url);
      } catch (err) {
        console.error(
          `Failed to load full image for image ID ${imageId}:`,
          err,
        );
      } finally {
        setLoading(false);
      }
    };

    loadFullImage();
  }, [imageId]);

  if (!imgUrl) {
    return null;
  }

  if (loading) return <ImageLoading size={128} msg="" />;
  if (failedUrl === imgUrl) return <NoImage />;

  return (
    <Image
      src={imgUrl}
      alt={`Image of ${speciesName}`}
      fill
      sizes="(max-width:768px) 100vw, 800px"
      className="object-contain m-1"
      onError={() => setFailedUrl(imgUrl)}
      unoptimized
    />
  );
}

function GalleryThumbnail({
  imageId,
  idx,
  speciesName,
}: {
  imageId: string;
  idx: number;
  speciesName: string;
}) {
  const [thumbUrl, setThumbUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [failedUrl, setFailedUrl] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const loadThumbnail = async () => {
      try {
        const url = await fetchThumbnailById(imageId);
        setThumbUrl(url);
      } catch (err) {
        console.error(`Failed to load thumbnail for image ID ${imageId}:`, err);
      } finally {
        setLoading(false);
      }
    };

    loadThumbnail();
  }, [imageId]);

  if (!thumbUrl) {
    return null;
  }
  return loading ? (
    <ImageLoading size={48} msg="" />
  ) : (
    <div className="relative w-full h-full">
      {failedUrl === thumbUrl ? (
        <NoImage className="text-[10px] [&>svg]:h-4 [&>svg]:w-4" />
      ) : (
        <Image
          src={thumbUrl}
          alt={`Thumbnail ${idx + 1} of ${speciesName}`}
          fill
          sizes="96px"
          className="object-contain"
          onError={() => setFailedUrl(thumbUrl)}
          unoptimized
        />
      )}
    </div>
  );
}
