"use client";

import { fetchSpeciesImage } from "@/lib/speciesList";
import Image from "next/image";
import React, { useEffect, useState } from "react";

export function SpeciesImages({ speciesName }: { speciesName: string }) {
  const [thumbnail, setThumbnail] = useState<string[]>([]);

  useEffect(() => {
    const fetchImage = async () => {
      // Fetch a list of image IDs for the species from speciesLists.ts file
      const image = await fetchSpeciesImage(speciesName);
      // Normalize to always be a string array
      if (Array.isArray(image)) {
        setThumbnail(image.filter(Boolean));
      } else if (image) {
        setThumbnail([image]);
      }
    };
    fetchImage();
  }, [speciesName]);

  return (
    <>
      {thumbnail && thumbnail.length > 0 && (
        <div className="flex flex-col gap-4">
          {/* Main image */}
          <div className="relative w-full aspect-video overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-900 backdrop-blur-lg shadow">
            <Image
              src={thumbnail[0]}
              alt={`Image of ${speciesName}`}
              fill
              sizes="(max-width:768px) 100vw, 600px"
              className="object-contain"
              priority
            />
          </div>

          {/* Thumbnails */}
          {thumbnail.length > 1 && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {thumbnail.map((img, idx) => (
                <button
                  key={img + idx}
                  type="button"
                  aria-label={`View image ${idx + 1} of ${speciesName}`}
                  title={`View image ${idx + 1} of ${speciesName}`}
                  onClick={() =>
                    setThumbnail((prev) => {
                      if (!prev) return prev;
                      if (idx === 0) return [...prev];
                      const reordered = [
                        prev[idx],
                        ...prev.filter((_, i) => i !== idx),
                      ];
                      return reordered;
                    })
                  }
                  className={`relative w-24 h-24 flex-shrink-0 rounded-lg overflow-hidden border transition-all ${
                    idx === 0
                      ? "ring-2 ring-blue-500 border-blue-500"
                      : "border-gray-300 dark:border-gray-700 hover:ring-2 hover:ring-blue-300"
                  }`}
                >
                  <Image
                    src={img}
                    alt={`Thumbnail ${idx + 1} of ${speciesName}`}
                    fill
                    sizes="96px"
                    className="object-cover"
                  />
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}
