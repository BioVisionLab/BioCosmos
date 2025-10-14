/*
"use client";

import ImageLoading from "@/components/ImageLoading";
import { fetchSpeciesImage } from "@/lib/speciesList";
import Image from "next/image";
import React, { useEffect, useState } from "react";

export function SpeciesImages({ speciesName }: { speciesName: string }) {
  const [thumbnail, setThumbnail] = useState<string[]>([]);

  useEffect(() => {
    const fetchImage = async () => {
      // Fetch a single image to be the first displayed image
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
    <div className="relative w-full aspect-video overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-900 backdrop-blur-lg shadow">
      {
      thumbnail.length === 0 ? ( <ImageLoading size={400} /> ) : 
      ( thumbnail.length > 0 && (
          <div className="flex flex-col gap-4">
            { // Main image 
             }

            <Image
              src={thumbnail[0]}
              alt={`Image of ${speciesName}`}
              fill
              sizes="(max-width:768px) 100vw, 600px"
              className="object-contain"
              priority
            />

            {// Thumbnails 
            }
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
        )
      )}
    </div>
  );
}
*/

// Test file rewrite

"use client";

import ImageLoading from "@/components/ImageLoading";
import {
  fetchImgById,
  fetchThumbnailById,
  fetchSpeciesImage,
} from "@/lib/speciesList";
import Image from "next/image";
import React, { useEffect, useRef, useState } from "react";

type GalleryItem = {
  id: string;
  thumb?: string;
  full?: string;
};

const TAXON_BASE = "http://127.0.0.1:8000/taxon";

/**
 * SpeciesImages
 * - requests image IDs from backend route /taxon/{species_name}/ids
 * - loads full image for the first ID via fetchImgById
 * - loads thumbnails (up to 5) for the following IDs via fetchThumbnailById
 * - clicking a thumbnail promotes it to the main image (loads full if needed)
 */
export function SpeciesImages({ speciesName }: { speciesName: string }) {
  const [items, setItems] = useState<GalleryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const createdUrls = useRef<string[]>([]);

  useEffect(() => {
    let mounted = true;

    const revokeAll = () => {
      createdUrls.current.forEach((u) => {
        try {
          URL.revokeObjectURL(u);
        } catch {
          /* ignore */
        }
      });
      createdUrls.current = [];
    };

    const loadIdsAndImages = async () => {
      setLoading(true);
      revokeAll();
      setItems([]);

      try {
        const cleanName = speciesName.toLowerCase().replace(/ /g, "_");
        const res = await fetch(`${TAXON_BASE}/${encodeURIComponent(cleanName)}/ids`);
        if (!mounted) return;

        if (!res.ok) {
          // treat 404 or other errors as "no IDs"
          // fallback: try the species-level single image endpoint
          try {
            const fallback = await fetchSpeciesImage(speciesName);
            if (!mounted) return;
            createdUrls.current.push(fallback);
            setItems([{ id: `species-fallback-${speciesName}`, full: fallback, thumb: fallback }]);
            return;
          } catch {
            if (!mounted) return;
            setItems([]);
            return;
          }
        }

        const payload = await res.json();

        // backend returns { species: ..., imageIds: [...] } in images.py
        let ids: string[] = [];
        if (Array.isArray(payload)) {
          ids = payload as string[];
        } else if (payload && Array.isArray(payload.imageIds)) {
          ids = payload.imageIds as string[];
        }

        if (!ids || ids.length === 0) {
          // fallback to single species image
          try {
            const fallback = await fetchSpeciesImage(speciesName);
            if (!mounted) return;
            createdUrls.current.push(fallback);
            setItems([{ id: `species-fallback-${speciesName}`, full: fallback, thumb: fallback }]);
            return;
          } catch {
            if (!mounted) return;
            setItems([]);
            return;
          }
        }

        // load full for first id
        const firstId = ids[0];
        const fullUrl = await fetchImgById(firstId).catch(() => undefined);
        if (fullUrl) createdUrls.current.push(fullUrl);

        // for following ids load up to 5 thumbnails
        const thumbIds = ids.slice(1, 1 + 5);
        const thumbPromises = thumbIds.map((id) =>
          fetchThumbnailById(id).catch(() => undefined)
        );
        const thumbResults = await Promise.all(thumbPromises);
        thumbResults.forEach((u) => {
          if (u) createdUrls.current.push(u);
        });

        const assembled: GalleryItem[] = [
          { id: firstId, full: fullUrl, thumb: thumbResults[0] ?? fullUrl },
          // include remaining thumbnails (if any) - note: we only requested up to 5
          ...thumbIds.map((id, i) => ({
            id,
            thumb: thumbResults[i],
          })),
        ];

        if (!mounted) return;
        setItems(assembled);
      } catch (err) {
        console.error("SpeciesImages load error:", err);
        if (mounted) setItems([]);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    loadIdsAndImages();

    return () => {
      mounted = false;
      // revoke created blob URLs
      createdUrls.current.forEach((u) => {
        try {
          URL.revokeObjectURL(u);
        } catch {
          /* ignore */
        }
      });
      createdUrls.current = [];
    };
  }, [speciesName]);

  const handleThumbnailClick = async (globalIndex: number) => {
    // globalIndex corresponds to index in items array; index 0 is main, so ignore clicking main
    if (globalIndex <= 0 || globalIndex >= items.length) return;

    const clicked = items[globalIndex];

    // optimistic reorder: move clicked to front
    setItems((prev) => {
      const copy = [...prev];
      const [it] = copy.splice(globalIndex, 1);
      copy.unshift(it);
      return copy;
    });

    // if the clicked item has no full image, fetch it
    if (!clicked.full) {
      try {
        const full = await fetchImgById(clicked.id);
        // track URL to revoke later
        createdUrls.current.push(full);
        setItems((prev) =>
          prev.map((it) => (it.id === clicked.id ? { ...it, full } : it))
        );
      } catch (err) {
        console.error("Failed to load full image for clicked thumbnail", err);
      }
    }
  };

  return (
    <div className="relative w-full aspect-video overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-900 backdrop-blur-lg shadow">
      {loading ? (
        <ImageLoading size={400} />
      ) : items.length === 0 ? (
        <div className="flex items-center justify-center h-full">No images</div>
      ) : (
        <div className="flex flex-col gap-4 h-full">
          {/* Main image */}
          <div className="relative w-full flex-grow">
            <Image
              src={items[0].full ?? items[0].thumb ?? ""}
              alt={`Image of ${speciesName}`}
              fill
              sizes="(max-width:768px) 100vw, 600px"
              className="object-contain"
              priority
            />
          </div>

          {/* Thumbnails (show up to 5 following images) */}
          {items.length > 1 && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {items.slice(1).map((it, idx) => {
                const globalIdx = idx + 1;
                return (
                  <button
                    key={it.id}
                    type="button"
                    aria-label={`View image ${globalIdx + 1} of ${speciesName}`}
                    title={`View image ${globalIdx + 1} of ${speciesName}`}
                    onClick={() => handleThumbnailClick(globalIdx)}
                    className="relative w-24 h-24 flex-shrink-0 rounded-lg overflow-hidden border border-gray-300 dark:border-gray-700 hover:ring-2 hover:ring-blue-300 transition-all"
                  >
                    <Image
                      src={it.thumb ?? it.full ?? ""}
                      alt={`Thumbnail ${globalIdx + 1} of ${speciesName}`}
                      fill
                      sizes="96px"
                      className="object-cover"
                    />
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}