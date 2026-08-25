"use client";
import React, { useEffect, useState } from "react";
import { NoData } from "@/components/NoData";

interface ImageMetadataProps {
  speciesName?: string;
  imageId?: string | null;
  prevImageIds?: string[];
  nextImageIds?: string[];
}

export default function ImageMetadata({
  speciesName,
  imageId,
  prevImageIds,
  nextImageIds,
}: ImageMetadataProps) {
  const [meta, setMeta] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const cacheRef = React.useRef<Map<string, any>>(new Map());

  const getSourceDbHref = (sourceUrl: unknown): string => {
    if (typeof sourceUrl !== "string") return "https://www.gbif.org";
    const trimmed = sourceUrl.trim();
    if (!trimmed) return "https://www.gbif.org";
    if (/^https?:\/\//i.test(trimmed)) return trimmed;
    if (/^www\./i.test(trimmed)) return `https://${trimmed}`;
    return "https://www.gbif.org";
  };

  // Helper to fetch metadata and store in cache
  const fetchAndCache = async (id: string) => {
    try {
      const res = await fetch(
        `/api/images/id/metadata?imageId=${encodeURIComponent(id)}`,
      );
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
    if (prevImageIds && prevImageIds.length)
      toPrefetch.push(...prevImageIds.slice(-2));
    if (nextImageIds && nextImageIds.length)
      toPrefetch.push(...nextImageIds.slice(0, 2));
    toPrefetch.forEach((id) => {
      if (!id) return;
      if (cacheRef.current.has(id)) return;
      void fetchAndCache(id);
    });
  }, [prevImageIds, nextImageIds]);

  return (
    <div className="p-5 bg-deep-mocha-100 dark:bg-deep-mocha-900 border border-deep-mocha-200 dark:border-deep-mocha-700 rounded-xl text-sm text-deep-mocha-700 dark:text-deep-mocha-400 leading-3.5">
      <h3 className="text-base font-semibold mb-2">Image Metadata</h3>
      <div className="flex flex-col gap-1">
        {loading ? (
          <div className="text-center text-sm text-deep-mocha-500">
            Loading metadata…
          </div>
        ) : !meta ? (
          <NoData
            text={imageId ? "No metadata available." : "No image selected."}
          />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-x-5 gap-y-2 items-start">
              {/* Left column: View, Source DB, Coordinates */}
              <div className="flex items-center min-w-0">
                <span className="font-sm text-deep-mocha-700 dark:text-deep-mocha-400 whitespace-nowrap">
                  View:
                </span>
                <span className="ml-1 truncate text-deep-mocha-700 dark:text-deep-mocha-400 capitalize">
                  {meta.class_dv
                    ? typeof meta.class_dv === "string"
                      ? meta.class_dv.toLowerCase()
                      : meta.class_dv
                    : "—"}
                </span>
              </div>
              <div className="flex items-center min-w-0">
                {meta.uri && (
                  <a
                    href={meta.uri}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-1 font-sm text-deep-mocha-700 dark:text-deep-mocha-400 underline truncate"
                    aria-label="Open image link"
                  >
                    Image Link
                  </a>
                )}
              </div>

              <div className="flex items-center min-w-0">
                <span className="font-sm text-deep-mocha-700 dark:text-deep-mocha-400 whitespace-nowrap">
                  Source DB:
                </span>
                <a
                  href={getSourceDbHref(meta.uuid)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-1 font-sm text-deep-mocha-700 dark:text-deep-mocha-400 underline truncate uppercase"
                  aria-label="Open source database link"
                >
                  {meta.source_db
                    ? typeof meta.source_db === "string"
                      ? meta.source_db
                      : meta.source_db
                    : "GBIF"}
                </a>
              </div>
              <div className="flex items-center min-w-0">
                {typeof meta.license === "string" &&
                meta.license.startsWith("http") ? (
                  <a
                    href={meta.license}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-1 font-sm text-deep-mocha-700 dark:text-deep-mocha-400 underline truncate"
                    aria-label="Open license"
                  >
                    License
                  </a>
                ) : (
                  <span className="text-deep-mocha-400 dark:text-deep-mocha-600">
                    —
                  </span>
                )}
              </div>

              <div className="flex items-center min-w-0">
                <span className="font-sm text-deep-mocha-700 dark:text-deep-mocha-400 whitespace-nowrap">
                  Coordinates:
                </span>
                <span className="ml-1 truncate text-deep-mocha-700 dark:text-deep-mocha-400">
                  {meta.lat || meta.lon
                    ? `${meta.lat ?? "—"}, ${meta.lon ?? "—"}`
                    : "—"}
                </span>
              </div>
              <div className="flex items-center min-w-0" />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
