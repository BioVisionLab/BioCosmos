"use client";

import React, { useEffect, useRef, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import { imageUrlById } from "@/lib/images";

/**
 * Metadata returned by `/api/images/id/metadata?imageId=...` for a single
 * specimen image. The backend may return additional fields; only the ones
 * the modal displays are typed here.
 */
export interface SpecimenImageMeta {
  class_dv?: string | null;
  lat?: number | null;
  lon?: number | null;
  source_db?: string | null;
  license?: string | null;
  uuid?: string | null;
  uri?: string | null;
  [key: string]: unknown;
}

// Module-level cache so metadata already fetched for an image (e.g. while
// browsing a species page) stays warm if the same image is opened again
// elsewhere (e.g. from search results) during the same session.
const metaCache = new Map<string, SpecimenImageMeta | null>();
const metaInFlight = new Map<string, Promise<SpecimenImageMeta | null>>();

async function fetchSpecimenMeta(
  id: string,
): Promise<SpecimenImageMeta | null> {
  if (!id) return null;
  if (metaCache.has(id)) return metaCache.get(id) ?? null;
  if (metaInFlight.has(id)) return (await metaInFlight.get(id)) ?? null;

  const request = (async () => {
    try {
      const res = await fetch(
        `/api/images/id/metadata?imageId=${encodeURIComponent(id)}`,
      );
      if (!res.ok) return null;
      const data = await res.json();
      metaCache.set(id, data ?? null);
      return data ?? null;
    } catch (err) {
      console.error("Error fetching image metadata:", err);
      return null;
    } finally {
      metaInFlight.delete(id);
    }
  })();

  metaInFlight.set(id, request);
  return (await request) ?? null;
}

function getSafeExternalHref(
  rawUrl: unknown,
  fallback = "https://www.gbif.org",
): string {
  if (typeof rawUrl !== "string") return fallback;
  const trimmed = rawUrl.trim();
  if (!trimmed) return fallback;

  const normalized = /^https?:\/\//i.test(trimmed)
    ? trimmed
    : /^www\./i.test(trimmed)
      ? `https://${trimmed}`
      : "";

  if (!normalized) return fallback;

  try {
    const parsed = new URL(normalized);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
    return fallback;
  } catch {
    return fallback;
  }
}

// Preload an image's bytes into the browser's HTTP cache without displaying
// it. `/api/images/id` serves images with a one-year immutable
// Cache-Control header, so once this resolves the same URL paints instantly
// from disk cache when it's actually shown.
function preloadImageBytes(url: string, onDone: () => void) {
  if (typeof window === "undefined") return;
  const img = new window.Image();
  img.onload = onDone;
  img.onerror = onDone; // don't get stuck retrying a broken image forever
  img.src = url;
}

export interface SpecimenImageModalProps {
  /**
   * Ordered ids of the images that can be browsed while the modal is open
   * (e.g. the currently displayed grid page or table page). Prev/next moves
   * within this list; a falsy entry (missing image) is skipped over.
   */
  ids: (string | null | undefined)[];
  /** Index into `ids` currently shown; `null` closes the modal. */
  openIndex: number | null;
  /** Called with the next index on navigation, or `null` to close. */
  onOpenIndexChange: (index: number | null) => void;
}

function SpecimenImageModal({
  ids,
  openIndex,
  onOpenIndexChange,
}: SpecimenImageModalProps) {
  const currentId =
    openIndex != null && openIndex >= 0 && openIndex < ids.length
      ? ids[openIndex]
      : null;
  const open = !!currentId;

  const [meta, setMeta] = useState<SpecimenImageMeta | null>(null);
  const [metaLoading, setMetaLoading] = useState(false);
  const [loadedIds, setLoadedIds] = useState<Set<string>>(new Set());
  const preloadingRef = useRef<Set<string>>(new Set());

  const markLoaded = (id: string) => {
    setLoadedIds((prev) => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  };

  // Find the next index in `direction` (+1/-1) whose id is usable, skipping
  // over empty slots and stopping at the ends (no wraparound).
  const findNavigableIndex = (
    from: number,
    direction: 1 | -1,
  ): number | null => {
    let i = from + direction;
    while (i >= 0 && i < ids.length) {
      if (ids[i]) return i;
      i += direction;
    }
    return null;
  };

  // Load metadata for the shown image and preload the full-size bytes for
  // its immediate neighbors so navigating there is instant.
  useEffect(() => {
    if (!open || !currentId || openIndex == null) return;
    let cancelled = false;

    setMeta(null);
    setMetaLoading(true);
    fetchSpecimenMeta(currentId).then((data) => {
      if (cancelled) return;
      setMeta(data);
      setMetaLoading(false);
    });

    const prevIdx = findNavigableIndex(openIndex, -1);
    const nextIdx = findNavigableIndex(openIndex, 1);
    [prevIdx, nextIdx].forEach((idx) => {
      if (idx == null) return;
      const id = ids[idx];
      if (!id) return;
      if (!loadedIds.has(id) && !preloadingRef.current.has(id)) {
        preloadingRef.current.add(id);
        preloadImageBytes(imageUrlById(id, "full"), () => markLoaded(id));
      }
      void fetchSpecimenMeta(id); // warm the metadata cache too
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, currentId]);

  // Lock background scroll while the modal is open.
  useEffect(() => {
    if (!open) return;
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = original;
    };
  }, [open]);

  // Keyboard: Escape closes, left/right arrows navigate.
  useEffect(() => {
    if (!open || openIndex == null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onOpenIndexChange(null);
      } else if (e.key === "ArrowLeft") {
        const idx = findNavigableIndex(openIndex, -1);
        if (idx != null) onOpenIndexChange(idx);
      } else if (e.key === "ArrowRight") {
        const idx = findNavigableIndex(openIndex, 1);
        if (idx != null) onOpenIndexChange(idx);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, openIndex, ids]);

  if (!open || !currentId || openIndex == null) return null;

  const prevIdx = findNavigableIndex(openIndex, -1);
  const nextIdx = findNavigableIndex(openIndex, 1);
  const imageLoaded = loadedIds.has(currentId);
  const imageUrl = imageUrlById(currentId, "full");

  return (
    <div
      className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/60"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        // close when clicking on backdrop
        if (e.target === e.currentTarget) onOpenIndexChange(null);
      }}
    >
      <div className="relative w-[45vw] max-w-[95vw] max-h-[95vh] flex flex-col items-center justify-center gap-4">
        <button
          onClick={() => onOpenIndexChange(null)}
          aria-label="Close full image"
          className="absolute -top-3 -right-3 z-40 flex items-center justify-center
            rounded-full p-2 bg-hunter-green-500 hover:bg-hunter-green-400
            dark:bg-hunter-green-600 dark:hover:bg-hunter-green-500
            text-gray border border-white/50 shadow-md hover:shadow-lg
            transition-all duration-200"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 text-white"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M10 8.586l4.95-4.95a1 1 0 111.414 1.414L11.414 10l4.95 4.95a1 1 0 01-1.414 1.414L10 11.414l-4.95 4.95a1 1 0 01-1.414-1.414L8.586 10 3.636 5.05A1 1 0 015.05 3.636L10 8.586z"
              clipRule="evenodd"
            />
          </svg>
        </button>

        {/* Formatting of pop-out image box (keep colors/borders but reserve a fixed box to prevent resizing) */}
        <div className="bg-deep-mocha-100 dark:bg-deep-mocha-900 border border-deep-mocha-500 dark:border-deep-mocha-600 rounded-xl p-4 w-full h-full flex-1 flex items-center justify-center relative">
          {/* left nav (aligned to image) */}
          <button
            onClick={() => prevIdx != null && onOpenIndexChange(prevIdx)}
            disabled={prevIdx == null}
            aria-label="Previous image"
            className={`absolute left-2 top-1/2 z-30 -translate-y-1/2 rounded-full p-2 transition-colors ${
              prevIdx == null
                ? "text-deep-mocha-400 cursor-not-allowed"
                : "text-white bg-black/30 hover:bg-white/10"
            }`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>

          <div className="relative w-full h-full flex items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              key={currentId}
              src={imageUrl}
              alt="Full size specimen"
              onLoad={() => markLoaded(currentId)}
              onError={() => markLoaded(currentId)}
              className="max-h-full max-w-full object-contain rounded-xl"
            />
            {/* Loading placeholder overlays the image until it (or a
                preload for it) has finished loading, so already-preloaded
                neighbors never show this at all. */}
            <div
              className={`absolute inset-0 flex items-center justify-center bg-deep-mocha-100 dark:bg-deep-mocha-900 rounded-xl transition-opacity ${
                imageLoaded ? "opacity-0 pointer-events-none" : "opacity-100"
              }`}
            >
              <ImageLoading size={250} />
            </div>
          </div>

          {/* right nav (aligned to image) */}
          <button
            onClick={() => nextIdx != null && onOpenIndexChange(nextIdx)}
            disabled={nextIdx == null}
            aria-label="Next image"
            className={`absolute right-2 top-1/2 z-30 -translate-y-1/2 rounded-full p-2 transition-colors ${
              nextIdx == null
                ? "text-deep-mocha-400 cursor-not-allowed"
                : "text-white bg-black/30 hover:bg-white/10"
            }`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>
        </div>

        {/* Metadata box below the image */}
        {(meta || metaLoading) && (
          <div className="mt-2 w-fit mx-auto">
            <div className="bg-deep-mocha-100 dark:bg-deep-mocha-900 border border-deep-mocha-500 dark:border-deep-mocha-600 rounded-xl p-4 text-xs text-deep-mocha-800 dark:text-white">
              <div className="flex flex-col gap-2">
                {metaLoading ? (
                  <div className="text-center text-sm text-deep-mocha-500">
                    Loading metadata…
                  </div>
                ) : (
                  <>
                    {meta?.class_dv && (
                      <div>
                        <span className="font-medium text-hunter-green-700 dark:text-hunter-green-500">
                          View:{" "}
                        </span>
                        <span className="text-deep-mocha-700 dark:text-white">
                          {typeof meta.class_dv === "string"
                            ? meta.class_dv.charAt(0).toUpperCase() +
                              meta.class_dv.slice(1)
                            : meta.class_dv}
                        </span>
                      </div>
                    )}
                    {(meta?.lat || meta?.lon) && (
                      <div>
                        <span className="font-medium text-hunter-green-700 dark:text-hunter-green-500">
                          Location:{" "}
                        </span>
                        <span className="text-deep-mocha-700 dark:text-white">
                          {meta?.lat ?? "—"}, {meta?.lon ?? "—"}
                        </span>
                      </div>
                    )}
                    {meta?.source_db && (
                      <div>
                        <span className="font-medium text-hunter-green-700 dark:text-hunter-green-500">
                          Source DB:{" "}
                        </span>
                        <span className="text-deep-mocha-700 dark:text-white uppercase">
                          {typeof meta.source_db === "string"
                            ? meta.source_db
                            : String(meta.source_db)}
                        </span>
                      </div>
                    )}

                    {/* Action buttons (License, Source, Image) - pill-shaped */}
                    <div className="mt-3 flex flex-wrap gap-2 justify-center">
                      {typeof meta?.license === "string" &&
                        meta.license.startsWith("http") && (
                          <a
                            href={meta.license}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-white dark:bg-deep-mocha-800 border border-deep-mocha-300 dark:border-deep-mocha-700 text-hunter-green-700 dark:text-hunter-green-300 hover:bg-hunter-green-50 dark:hover:bg-hunter-green-900"
                            aria-label="Open license"
                          >
                            License
                          </a>
                        )}
                      {(meta?.uuid || meta?.source_db) && (
                        <a
                          href={getSafeExternalHref(meta?.uuid)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-white dark:bg-deep-mocha-800 border border-deep-mocha-300 dark:border-deep-mocha-700 text-hunter-green-700 dark:text-hunter-green-300 hover:bg-hunter-green-50 dark:hover:bg-hunter-green-900"
                          aria-label="Open source link"
                        >
                          Source Link
                        </a>
                      )}
                      {typeof meta?.uri === "string" && meta.uri && (
                        <a
                          href={meta.uri}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-white dark:bg-deep-mocha-800 border border-deep-mocha-300 dark:border-deep-mocha-700 text-hunter-green-700 dark:text-hunter-green-300 hover:bg-hunter-green-50 dark:hover:bg-hunter-green-900"
                          aria-label="Open image link"
                        >
                          Image Link
                        </a>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export { SpecimenImageModal };
