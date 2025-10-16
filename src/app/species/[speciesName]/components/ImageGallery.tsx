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
 * - loads thumbnails for the next 5 IDs via fetchThumbnailById
 * - clicking a thumbnail selects it as the main image WITHOUT reordering
 */
export function SpeciesImages({ speciesName }: { speciesName: string }) {
  const [items, setItems] = useState<GalleryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIndex, setSelectedIndex] = useState(0); // which image is shown large
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
      setSelectedIndex(0);
      revokeAll();
      setItems([]);

      try {
        const cleanName = speciesName.toLowerCase().replace(/ /g, "_");
        const res = await fetch(
          `${TAXON_BASE}/${encodeURIComponent(cleanName)}/ids`
        );
        if (!mounted) return;

        if (!res.ok) {
          // fallback: try species-level single image endpoint
          try {
            const fallback = await fetchSpeciesImage(speciesName);
            if (!mounted) return;
            createdUrls.current.push(fallback);
            setItems([
              {
                id: `species-fallback-${speciesName}`,
                full: fallback,
                thumb: fallback,
              },
            ]);
            return;
          } catch {
            if (!mounted) return;
            setItems([]);
            return;
          }
        }

        const payload = await res.json();

        // payload may be an array of ids or an object with imageIds
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
            setItems([
              {
                id: `species-fallback-${speciesName}`,
                full: fallback,
                thumb: fallback,
              },
            ]);
            return;
          } catch {
            if (!mounted) return;
            setItems([]);
            return;
          }
        }

        // limit total thumbnails to 6 images (1 main + 5 thumbs)
        const total = 6;
        const selected = 0; // default selected index (first)
        const idsToUse = ids.slice(0, total);

        // fetch full for first id (or the selected index)
        const firstId = idsToUse[selected];
        const fullUrl = await fetchImgById(firstId).catch(() => undefined);
        if (fullUrl) createdUrls.current.push(fullUrl);

        // fetch thumbnails for all ids (we show thumbs for all positions but first may reuse full if no thumb)
        const thumbPromises = idsToUse.map((id) =>
          fetchThumbnailById(id).catch(() => undefined)
        );
        const thumbResults = await Promise.all(thumbPromises);
        thumbResults.forEach((u) => {
          if (u) createdUrls.current.push(u);
        });

        const assembled: GalleryItem[] = idsToUse.map((id, i) => ({
          id,
          full: i === selected ? fullUrl : undefined,
          thumb: thumbResults[i] ?? undefined,
        }));

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

  const handleThumbnailClick = async (idx: number) => {
    // keep items order fixed; only change selectedIndex
    if (idx < 0 || idx >= items.length) return;
    setSelectedIndex(idx);

    const clicked = items[idx];
    if (!clicked.full) {
      try {
        const full = await fetchImgById(clicked.id);
        createdUrls.current.push(full);
        setItems((prev) =>
          prev.map((it, i) => (i === idx ? { ...it, full } : it))
        );
      } catch (err) {
        console.error("Failed to load full image for selected thumbnail", err);
      }
    }
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
            <Image
              src={
                items[selectedIndex]?.full ?? items[selectedIndex]?.thumb ?? ""
              }
              alt={`Image of ${speciesName}`}
              fill
              sizes="(max-width:768px) 100vw, 600px"
              className="object-contain"
              priority
            />
          </div>

          {/* Thumbnails (show up to 6 total images, keeping order) */}
          {items.length > 1 && (
            <div className="flex gap-3 overflow-x-auto">
              {/* increased gap and top padding */}
              {items.map((it, idx) => (
                <button
                  key={it.id}
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
                  <Image
                    src={it.thumb ?? it.full ?? ""}
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
    </div>
  );
}
