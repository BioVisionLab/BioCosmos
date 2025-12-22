"use client";

import { ImageLoading } from "@/components/Loadings";
import {
  fetchImgById,
  fetchThumbnailById,
  fetchSpeciesImageIds,
} from "@/lib/images";
import Image from "next/image";
import React, { useEffect, useState } from "react";

export function SpeciesImageGallery({ speciesName }: { speciesName: string }) {
  const [items, setItems] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

  useEffect(() => {
    const loadIdsAndImages = async () => {
      setLoading(true);
      setSelectedIndex(0);
      setItems([]);

      try {
        const image_ids = await fetchSpeciesImageIds(speciesName, 8);
        if (image_ids.length === 0) {
          setItems([]);
          return;
        }
        setItems(image_ids);
      } catch (err) {
        console.error("SpeciesImages load error:", err);
        setItems([]);
      } finally {
        setLoading(false);
      }
    };

    loadIdsAndImages();
  }, [speciesName]);

  const handleThumbnailClick = (index: number) => {
    setSelectedIndex(index);
  };

  return (
    <div
      className={`relative w-full aspect-video overflow-hidden rounded-xl bg-gray-100 dark:bg-gray-900 ${
        loading
          ? "flex items-center justify-center border border-gray-200 dark:border-gray-700"
          : ""
      }`}
    >
      {loading ? (
        <ImageLoading size={400} />
      ) : items.length === 0 ? (
        <div className="flex items-center justify-center h-full">No images</div>
      ) : (
        <div className="flex flex-col gap-3 h-full">
          {/* add outer padding so thumbs have breathing room */}
          {/* Main image */}
          <div className="relative w-full flex-grow rounded-xl overflow-hidden border  border-gray-200 dark:border-gray-700">
            {/* Left/right circular nav buttons (scroll through the 8 images) */}
            <button
              aria-label="Previous image"
              onClick={() => handleThumbnailClick(Math.max(0, selectedIndex - 1))}
              disabled={selectedIndex <= 0}
              className={`absolute left-3 top-1/2 -translate-y-1/2 z-20 rounded-full p-2 transition-colors ${
                selectedIndex <= 0
                  ? "text-gray-400 cursor-not-allowed bg-transparent"
                  : "text-white bg-teal-800 hover:bg-teal-700 shadow-md"
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>

            <GalleryFullImage
              imageId={items[selectedIndex]}
              speciesName={speciesName}
            />

            <button
              aria-label="Next image"
              onClick={() => handleThumbnailClick(Math.min(items.length - 1, selectedIndex + 1))}
              disabled={selectedIndex >= items.length - 1}
              className={`absolute right-3 top-1/2 -translate-y-1/2 z-20 rounded-full p-2 transition-colors ${
                selectedIndex >= items.length - 1
                  ? "text-gray-400 cursor-not-allowed bg-transparent"
                  : "text-white bg-teal-800 hover:bg-teal-700 shadow-md"
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
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
                      ? "border-emerald-300"
                      : "border-gray-300 dark:border-gray-700 hover:border-teal-600"
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

  useEffect(() => {
    setLoading(true);
    const loadFullImage = async () => {
      try {
        const url = await fetchImgById(imageId);
        setImgUrl(url);
      } catch (err) {
        console.error(
          `Failed to load full image for image ID ${imageId}:`,
          err
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

  return loading ? (
    <ImageLoading size={128} msg="" />
  ) : (
    <Image
      src={imgUrl}
      alt={`Image of ${speciesName}`}
      fill
      sizes="(max-width:768px) 100vw, 800px"
      className="object-contain"
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
    <Image
      src={thumbUrl}
      alt={`Thumbnail ${idx + 1} of ${speciesName}`}
      fill
      sizes="96px"
      className="object-cover"
    />
  );
}
