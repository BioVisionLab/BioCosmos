"use client";

import React, { useEffect, useRef, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import { imageUrlById } from "@/lib/images";
import {
  SpecimenImageMeta,
  acceptedDisplayName,
  coordinatesOf,
  localityOf,
  nameWasUpdated,
  taxonomyOf,
} from "@/lib/imageMetadata";
import { CoordinateStatusBadge, TaxonStatusBadge } from "@/components/CodeHint";
import {
  METADATA_LABEL,
  METADATA_VALUE,
  MetadataLinks,
} from "@/components/ImageMetadataFields";
import { cleanSpeciesName } from "@/lib/names";

/**
 * Metadata returned by `/api/images/id/metadata?imageId=...` for a single
 * specimen image. The backend may return additional fields; only the ones
 * the modal displays are typed here.
 */
// Defined in @/lib/imageMetadata and re-exported here, where it used to
// live, so existing importers keep working.
export type { SpecimenImageMeta };

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

        {/* Combined image and metadata box */}
        <div className="bg-deep-mocha-100 dark:bg-deep-mocha-900 border border-deep-mocha-500 dark:border-deep-mocha-600 rounded-xl p-4 w-full h-full flex-1 flex flex-col items-center justify-start relative">
          {/* Image container with nav buttons */}
          <div className="w-full flex-1 flex items-center justify-center relative">
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

          {/* No card of its own: the gallery box around it already provides
              the border, so a second one only added dead space. The rule
              above separates the image from the metadata, and the rules
              inside separate the metadata's own groups. Type scale and field
              order still match the panel under the species gallery. */}
          {(meta || metaLoading) && (
            <div className="mt-4 w-[30vw] border-t border-deep-mocha-300 dark:border-deep-mocha-700 pt-3 text-sm text-deep-mocha-700 dark:text-deep-mocha-300">
              <div>
                <div className="flex flex-col gap-1">
                  {metaLoading ? (
                    <div className="text-center text-sm text-deep-mocha-500">
                      Loading metadata…
                    </div>
                  ) : (
                    <>
                      {meta?.class_dv && (
                        <div>
                          <span className={METADATA_LABEL}>
                            View:{" "}
                          </span>
                          <span className={METADATA_VALUE}>
                            {typeof meta.class_dv === "string"
                              ? meta.class_dv.charAt(0).toUpperCase() +
                                meta.class_dv.slice(1)
                              : meta.class_dv}
                          </span>
                        </div>
                      )}
                      <div>
                        <span className={METADATA_LABEL}>Source DB: </span>
                        <span className={`uppercase ${METADATA_VALUE}`}>
                          {typeof meta?.source_db === "string" && meta.source_db
                            ? meta.source_db
                            : "GBIF"}
                        </span>
                      </div>
                      {/* The written locality, then the coordinate and the
                          verdict on it. Both rows are rendered even when
                          empty, and in this order, so this panel and the one
                          under the species gallery read the same way. */}
                      <div>
                        <span className={METADATA_LABEL}>
                          Locality:{" "}
                        </span>
                        <span className={METADATA_VALUE}>
                          {localityOf(meta)?.display ?? "—"}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span>
                          <span className={METADATA_LABEL}>
                            Coordinates:{" "}
                          </span>
                          <span className={METADATA_VALUE}>
                            {meta?.lat || meta?.lon
                              ? `${meta?.lat ?? "—"}, ${meta?.lon ?? "—"}`
                              : "—"}
                          </span>
                        </span>
                        {coordinatesOf(meta) ? (
                          <CoordinateStatusBadge
                            validation={coordinatesOf(meta)}
                          />
                        ) : null}
                      </div>


                      {/* The same taxonomic update the species-page panel
                          shows, so the two views never disagree. */}
                      {(() => {
                        const taxonomy = taxonomyOf(meta);
                        if (!taxonomy) return null;
                        const accepted = acceptedDisplayName(taxonomy);
                        const showRecorded = nameWasUpdated(taxonomy);
                        return (
                          // Ruled off from the fields above, the same way the
                          // species-page panel separates its taxonomy block.
                          <div className="mt-1 pt-2 border-t border-deep-mocha-200 dark:border-deep-mocha-700 flex flex-col gap-1">
                            <div className="flex flex-wrap items-start gap-2">
                              <span className={METADATA_LABEL}>
                                Taxonomy:
                              </span>
                              <TaxonStatusBadge update={taxonomy} showMethod />
                            </div>
                            {accepted && (
                              <div>
                                <span className={METADATA_LABEL}>
                                  Accepted name:{" "}
                                </span>
                                <i className={`italic ${METADATA_VALUE}`}>
                                  {accepted}
                                </i>
                              </div>
                            )}
                            {/* This is a view of one image, so what that
                                record actually said belongs here just as it
                                does in the species-page panel. */}
                            {showRecorded && taxonomy.inputName && (
                              <div>
                                <span className={METADATA_LABEL}>
                                  Recorded as:{" "}
                                </span>
                                <i className="italic text-deep-mocha-500 dark:text-deep-mocha-400">
                                  {cleanSpeciesName(taxonomy.inputName)}
                                </i>
                                {taxonomy.recordedRank &&
                                taxonomy.recordedRank.toLowerCase() !==
                                  "species" ? (
                                  <span className="text-deep-mocha-500 dark:text-deep-mocha-400">
                                    {" "}
                                    ({taxonomy.recordedRank.toLowerCase()})
                                  </span>
                                ) : null}
                              </div>
                            )}
                          </div>
                        );
                      })()}

                      {meta ? <MetadataLinks meta={meta} /> : null}
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export { SpecimenImageModal };
