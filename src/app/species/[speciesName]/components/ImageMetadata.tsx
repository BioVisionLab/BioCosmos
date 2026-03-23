"use client";
import React, { useEffect, useState } from "react";
import { NoData } from "@/components/NoData";

interface ImageMetadataProps {
  speciesName?: string;
  imageId?: string | null;
  prevImageIds?: string[];
  nextImageIds?: string[];
}

export default function ImageMetadata({ speciesName, imageId, prevImageIds, nextImageIds }: ImageMetadataProps) {
  const [meta, setMeta] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const cacheRef = React.useRef<Map<string, any>>(new Map());

  // Helper to fetch metadata and store in cache
  const fetchAndCache = async (id: string) => {
    try {
      const res = await fetch(`/api/images/id/metadata?imageId=${encodeURIComponent(id)}`);
      if (!res.ok) return null;
      const data = await res.json();
      cacheRef.current.set(id, data ?? null);
      return data ?? null;
    } catch (err) {
      console.error("Error fetching image metadata:", err);
      return null;
    }
  };

  // Main effect: when imageId changes, display from cache if available otherwise fetch
  useEffect(() => {
    if (!imageId) {
      setMeta(null);
      setLoading(false);
      return;
    }

    let ignore = false;

    const run = async () => {
      const cached = cacheRef.current.get(imageId);
      if (cached !== undefined) {
        setMeta(cached);
        setLoading(false);
        return;
      }

      setMeta(null);
      setLoading(true);
      const data = await fetchAndCache(imageId);
      if (!ignore) setMeta(data);
      if (!ignore) setLoading(false);
    };

    void run();
    return () => {
      ignore = true;
    };
  }, [imageId]);

  // Prefetch neighbor metadata in background (up to two in either direction)
  useEffect(() => {
    const toPrefetch: Array<string | undefined | null> = [];
    if (prevImageIds && prevImageIds.length) toPrefetch.push(...prevImageIds.slice(-2));
    if (nextImageIds && nextImageIds.length) toPrefetch.push(...nextImageIds.slice(0, 2));
    toPrefetch.forEach((id) => {
      if (!id) return;
      if (cacheRef.current.has(id)) return;
      void fetchAndCache(id);
    });
  }, [prevImageIds, nextImageIds]);

  return (
    <div className="p-4 bg-gray-100 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl text-xs text-gray-800 dark:text-white leading-4">
      <h3 className="text-base font-semibold mb-1">Image Metadata</h3>
      <div className="flex flex-col gap-1">
        {loading ? (
          <div className="text-center text-xs text-gray-500">Loading metadata…</div>
        ) : !meta ? (
          <NoData text={imageId ? "No metadata available." : "No image selected."} />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 items-center">
              {/* View + Source Link */}
              <div className="flex items-center min-w-0">
                <span className="font-medium text-emerald-700 dark:text-emerald-500 whitespace-nowrap">View:</span>
                <span className="ml-1 truncate text-gray-700 dark:text-white">
                  {meta.class_dv ? (typeof meta.class_dv === 'string' ? meta.class_dv.charAt(0).toUpperCase() + meta.class_dv.slice(1) : meta.class_dv) : "—"}
                </span>
              </div>
              <div className="flex items-center min-w-0">
                {meta.uuid && (
                  <a
                    href={meta.uuid}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-1 text-emerald-700 dark:text-emerald-300 underline truncate"
                    aria-label="Open source link"
                  >
                    Source Link
                  </a>
                )}
              </div>

              {/* Source DB + Image Link */}
              <div className="flex items-center min-w-0">
                <span className="font-medium text-emerald-700 dark:text-emerald-500 whitespace-nowrap">Source DB:</span>
                <span className="ml-1 truncate text-gray-700 dark:text-white">
                  {meta.source_db ? (typeof meta.source_db === 'string' ? meta.source_db.charAt(0).toUpperCase() + meta.source_db.slice(1) : meta.source_db) : "—"}
                </span>
              </div>
              <div className="flex items-center min-w-0">
                {meta.uri && (
                  <a
                    href={meta.uri}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-1 text-emerald-700 dark:text-emerald-300 underline truncate"
                    aria-label="Open image link"
                  >
                    Image Link
                  </a>
                )}
              </div>

              {/* Location + License (both optional) */}
              <div className="flex items-center min-w-0">
                <span className="font-medium text-emerald-700 dark:text-emerald-500 whitespace-nowrap">Location:</span>
                <span className="ml-1 truncate text-gray-700 dark:text-white">
                  {(meta.lat || meta.lon) ? `${meta.lat ?? "—"}, ${meta.lon ?? "—"}` : "—"}
                </span>
              </div>
              <div className="flex items-center min-w-0">
                {typeof meta.license === "string" && meta.license.startsWith("http") ? (
                  <a
                    href={meta.license}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-1 text-emerald-700 dark:text-emerald-300 underline truncate"
                    aria-label="Open license"
                  >
                    License
                  </a>
                ) : (
                  <span className="text-gray-400 dark:text-gray-600">—</span>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
