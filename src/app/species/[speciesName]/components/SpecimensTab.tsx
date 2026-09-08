"use client";

import React, { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ImageLoading } from "@/components/Loadings";
import { IconContainer } from "@/components/IconContainer";
import { ButterflyComplex } from "@/components/ui/Butterfly";
import { SpecimenData, fetchSpecimenData } from "@/lib/specimens";
import { formatNumberToLocaleString } from "@/lib/textUtils";
import {
  fetchThumbnailById,
  fetchSpeciesImageIds,
} from "@/lib/images";
import ImageUmap from "./ImageUmap";
import Tips from "@/components/Tips";
import PaginationControls from "@/components/PaginationControls";
import { SpecimenImageModal } from "@/components/SpecimenImageModal";

interface SpecimensTabProps {
  // keep backward compatibility: callers may pass specimens array
  specimens?: any[] | undefined;
  // preferred: pass speciesName to fetch image IDs from backend
  speciesName?: string;
  // when true, show full gallery with pagination; when false show only first 16 images
  showAll?: boolean;
  // when false, hide the Image UMAP / similarity box
  showUmap?: boolean;
  // when false, hide the image-count header (used by the standalone gallery)
  showImageCount?: boolean;
  // optional: preloaded specimen metadata to avoid refetching on gallery pages
  initialSpecimenData?: SpecimenData | null;
}

type ThumbItem = {
  id: string;
  thumbUrl?: string;
};

const SpecimensTab: React.FC<SpecimensTabProps> = ({
  specimens,
  speciesName,
  showAll: propsShowAll,
  showUmap: propsShowUmap,
  showImageCount: propsShowImageCount,
  initialSpecimenData,
}) => {
  const [items, setItems] = useState<ThumbItem[]>([]); // current page items
  // initialize specimen metadata from optional prop to avoid re-fetching
  const [specimenData, setSpecimenData] = useState<SpecimenData | null>(
    initialSpecimenData ?? null,
  );
  const [specimenLoading, setSpecimenLoading] = useState(false);
  const [allIds, setAllIds] = useState<string[] | null>(null); // all image ids for species
  const allIdsRef = useRef<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const createdUrls = useRef<string[]>([]);
  // pagination
  const PAGE_SIZE = 24; // images per page
  // Offset paging works against the backend now, so there is no need to
  // over-fetch IDs up front; loadNextChunk pulls the rest on demand.
  const INITIAL_PAGES = 2; // initial pages to request (24 * 2 = 48)
  // preview size for species overview (two rows)
  const MAX_PREVIEW = 16;
  const [currentPage, setCurrentPage] = useState<number>(1); // 1-based
  // `displayPage` is the visual page highlighted in the UI. We update it
  // immediately on user actions to provide instant feedback; `currentPage`
  // represents the committed page once data has been loaded.
  const [displayPage, setDisplayPage] = useState<number>(1);
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);
  const [exhaustedIds, setExhaustedIds] = useState<boolean>(false);

  // simple cache of fetched thumbnail URLs by image id
  const thumbCache = useRef<Map<string, string | undefined>>(new Map());
  const showAll = propsShowAll ?? false;
  const showUmap = propsShowUmap ?? true;
  const showImageCount = propsShowImageCount ?? true;
  // track which thumbnails have finished loading (by id)
  const [loadedThumbIds, setLoadedThumbIds] = useState<Set<string>>(new Set());
  // index into `modalPageIds` (below) of the specimen open in the full-image
  // modal; `null` means the modal is closed. The modal itself owns all
  // full-image/metadata fetching, caching and neighbor preloading.
  const [openIndexInPage, setOpenIndexInPage] = useState<number | null>(null);

  // moved logic into named helpers below and call them here
  useEffect(() => {
    let mountedMeta = true;
    let mounted = true;

    const run = async () => {
      // Only load remote metadata when an initial specimen metadata object
      // hasn't been provided by the parent (e.g. gallery page).
      if (!initialSpecimenData) await loadMeta(speciesName, mountedMeta);

      if (!mounted) return;

      if (speciesName) {
        if (showAll) {
          await loadFromSpecies(nameOr(speciesName), mounted);
        } else {
          await loadPreview(nameOr(speciesName), mounted);
        }
      } else if (!speciesName && specimens && specimens.length > 0) {
        await loadFromSpecimensFallback(specimens, mounted);
      } else {
        // no speciesName and no specimens
        setItems([]);
      }
    };

    run();

    return () => {
      mounted = false;
      mountedMeta = false;
      revokeAll();
    };
  }, [speciesName, specimens, showAll]);

  // load a small preview (first `MAX_PREVIEW` ids) for the overview page
  async function loadPreview(name: string, mountedFlag = true) {
    setLoading(true);
    setError(null);
    setItems([]);
    revokeAll();
    thumbCache.current.clear();
    setAllIds(null);
    allIdsRef.current = null;
    setCurrentPage(1);
    setDisplayPage(1);
    setExhaustedIds(false);

    try {
      const limit = MAX_PREVIEW;
      const ids = await fetchSpeciesImageIds(name, limit, 0);
      if (!mountedFlag) return;

      if (!ids || ids.length === 0) {
        setError("No image IDs returned for this species.");
        setItems([]);
        return;
      }

      setAllIds(ids);
      allIdsRef.current = ids;
      // if backend returned fewer than the requested preview, we've loaded all available ids
      if (ids.length < limit) setExhaustedIds(true);
      if (specimenData?.imageCounts && ids.length >= specimenData.imageCounts)
        setExhaustedIds(true);
      const toUse = ids.slice(0, limit);
      const results = await fetchThumbnailsForIds(toUse);
      if (!mountedFlag) return;
      results.forEach((r) => {
        if (r.url) createdUrls.current.push(r.url);
        thumbCache.current.set(r.id, r.url);
      });
      setItems(results.map((r) => ({ id: r.id, thumbUrl: r.url })));
    } catch (err) {
      console.error("SpecimensTab preview load error:", err);
      if (mountedFlag) setError("Failed to load specimen thumbnails.");
    } finally {
      if (mountedFlag) setLoading(false);
    }
  }

  // helper to normalize a name string
  const nameOr = (n?: string) => n ?? "";

  // load specimen metadata (image count) separately and show in header
  async function loadMeta(name?: string, mountedFlag = true) {
    if (!name) {
      setSpecimenData(null);
      return;
    }
    setSpecimenLoading(true);
    try {
      const data = await fetchSpecimenData(name);
      if (!mountedFlag) return;
      setSpecimenData(data ?? null);
    } catch (err) {
      console.error("Failed to fetch specimen metadata:", err);
      if (mountedFlag) setSpecimenData(null);
    } finally {
      if (mountedFlag) setSpecimenLoading(false);
    }
  }

  // revoke any created object URLs and clear caches
  function revokeAll() {
    createdUrls.current.forEach((u) => {
      try {
        URL.revokeObjectURL(u);
      } catch {
        /* ignore */
      }
    });
    createdUrls.current = [];
  }

  // fetch a list of thumbnails for given ids (defensive: returns url undefined on failure)
  async function fetchThumbnailsForIds(ids: string[]) {
    const promises = ids.map((id) =>
      fetchThumbnailById(id)
        .then((url) => ({ id, url }))
        .catch(() => ({ id, url: undefined })),
    );
    return Promise.all(promises);
  }

  // load image ids and initial thumbnails for a species
  async function loadFromSpecies(name: string, mountedFlag = true) {
    setLoading(true);
    setError(null);
    setItems([]);
    revokeAll();
    thumbCache.current.clear();
    setAllIds(null);
    allIdsRef.current = null;
    setCurrentPage(1);
    setDisplayPage(1);
    setExhaustedIds(false);

    try {
      const initialLimit = PAGE_SIZE * INITIAL_PAGES;
      const ids = await fetchSpeciesImageIds(name, initialLimit, 0);
      if (!mountedFlag) return;

      if (!ids || ids.length === 0) {
        setError("No image IDs returned for this species.");
        setItems([]);
        return;
      }

      setAllIds(ids);
      allIdsRef.current = ids;
      // if backend returned fewer than the initial request, we've loaded all available ids
      if (ids.length < initialLimit) setExhaustedIds(true);
      // if specimen metadata is known and we already fetched all images, mark exhausted
      if (specimenData?.imageCounts && ids.length >= specimenData.imageCounts)
        setExhaustedIds(true);
      const toUse = ids.slice(0, PAGE_SIZE);
      const results = await fetchThumbnailsForIds(toUse);
      if (!mountedFlag) return;
      results.forEach((r) => {
        thumbCache.current.set(r.id, r.url);
      });
      setItems(results.map((r) => ({ id: r.id, thumbUrl: r.url })));
      // prefetch next two pages after initial load
      void prefetchNextPages(1, 2);
    } catch (err) {
      console.error("SpecimensTab load error:", err);
      if (mountedFlag) setError("Failed to load specimen thumbnails.");
    } finally {
      if (mountedFlag) setLoading(false);
    }
  }

  // Load the next chunk (one page worth of IDs) and append them.
  const loadNextChunk = async () => {
    if (!speciesName) return;
    if (isLoadingMore) return;
    setIsLoadingMore(true);
    try {
      const existing = allIds ?? [];
      const offset = existing.length;
      const fetched = await fetchSpeciesImageIds(
        speciesName,
        PAGE_SIZE,
        offset,
      );
      // if backend returns fewer than requested, we've exhausted available ids
      if (!fetched || fetched.length === 0) {
        setExhaustedIds(true);
        return;
      }

      // determine deduped additions and new full list
      const deduped = fetched.filter((id) => !existing.includes(id));
      // if backend returned only duplicates (no progress), treat as exhausted
      if (deduped.length === 0) {
        setExhaustedIds(true);
        return;
      }
      const newAll = [...existing, ...deduped];
      // update state with the new list (use functional set to avoid race)
      setAllIds(newAll);
      allIdsRef.current = newAll;
      // mark that we've appended extra pages beyond the initial load

      // compute the page index of the first newly added item using the previous length
      const firstNewIndex = existing.length;
      const firstNewPage = Math.floor(firstNewIndex / PAGE_SIZE) + 1;
      // load thumbnails for that page
      const pageStart = (firstNewPage - 1) * PAGE_SIZE;
      const pageIds = newAll.slice(pageStart, pageStart + PAGE_SIZE);
      const results = await fetchThumbnailsForIds(pageIds);
      results.forEach((r) => {
        if (r.url) {
          createdUrls.current.push(r.url);
          thumbCache.current.set(r.id, r.url);
        } else {
          thumbCache.current.set(r.id, undefined);
        }
      });
      setItems(results.map((r) => ({ id: r.id, thumbUrl: r.url })));
      if (fetched.length < PAGE_SIZE) setExhaustedIds(true);
    } catch (err) {
      console.error("Failed to load next chunk of thumbnails:", err);
      setError("Failed to load more thumbnails.");
    } finally {
      setIsLoadingMore(false);
    }
  };

  // fallback when a specimens array is passed in (client-provided data)
  async function loadFromSpecimensFallback(
    specimensArr: any[],
    mountedFlag = true,
  ) {
    const idsFromSpecimens: string[] = specimensArr
      .map((s) => s?.imgId ?? s?.imageId ?? s?.id)
      .filter(Boolean);

    if (idsFromSpecimens.length === 0) {
      const built: ThumbItem[] = specimensArr.map((s) => ({
        id: s?.id ?? s?.catalogNumber ?? Math.random().toString(),
        thumbUrl: s?.imageUrl,
      }));
      setItems(built.slice(0, PAGE_SIZE));
      const builtIds = built.map((b) => b.id);
      setAllIds(builtIds);
      allIdsRef.current = builtIds;
      return;
    }

    setLoading(true);
    setAllIds(idsFromSpecimens);
    allIdsRef.current = idsFromSpecimens;
    // if the provided specimens list is small, mark as exhausted (no remote load expected)
    if (idsFromSpecimens.length <= PAGE_SIZE) setExhaustedIds(true);
    const pageIds = idsFromSpecimens.slice(0, PAGE_SIZE);
    try {
      const results = await fetchThumbnailsForIds(pageIds);
      results.forEach((r) => {
        if (r.url) createdUrls.current.push(r.url);
        thumbCache.current.set(r.id, r.url);
      });
      if (mountedFlag)
        setItems(results.map((r) => ({ id: r.id, thumbUrl: r.url })));
      // sync display/committed page
      setCurrentPage(1);
      setDisplayPage(1);
      // prefetch next two pages for client-provided specimen lists
      void prefetchNextPages(1, 2);
    } catch (err) {
      console.error(err);
      if (mountedFlag) setError("Failed to load thumbnails from specimens.");
    } finally {
      if (mountedFlag) setLoading(false);
    }
  }

  // cleanup meta loader on unmount
  useEffect(() => {
    return () => {
      setSpecimenLoading(false);
    };
  }, []);

  // helper to load thumbnails for a given page (1-based)
  const loadPage = async (page: number) => {
    // Use the ref (synchronously updated) when available to avoid stale
    // `allIds` state during rapid append operations. Fallback to `allIds`.
    const idsSource = allIdsRef.current ?? allIds ?? [];
    if (idsSource.length === 0) return;
    const total = idsSource.length;
    const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const p = Math.max(1, Math.min(pageCount, page));
    // Do not aggressively change the displayed page here — we'll commit
    // both `currentPage` and `displayPage` after data is loaded to keep the
    // UI stable and avoid flicker/back-and-forth highlights.
    setLoading(true);
    setError(null);

    const start = (p - 1) * PAGE_SIZE;
    const pageIds = idsSource.slice(start, start + PAGE_SIZE);

    // fetch thumbnails for ids not in cache
    const fetchPromises = pageIds.map((id) => {
      const cached = thumbCache.current.get(id);
      if (cached !== undefined) return Promise.resolve({ id, url: cached });
      return fetchThumbnailById(id)
        .then((url) => ({ id, url }))
        .catch(() => ({ id, url: undefined }));
    });

    try {
      const results = await Promise.all(fetchPromises);
      results.forEach((r) => {
        if (r.url) {
          createdUrls.current.push(r.url);
          thumbCache.current.set(r.id, r.url);
        } else {
          thumbCache.current.set(r.id, undefined);
        }
      });
      setItems(results.map((r) => ({ id: r.id, thumbUrl: r.url })));
      // Prefetch thumbnails for the next 2 pages in the background to make
      // short hops feel instant.
      void prefetchNextPages(p, 2);
      // commit the page after successful load
      setCurrentPage(p);
      setDisplayPage(p);
    } catch (err) {
      console.error("Failed to load page thumbnails.", err);
      setError("Failed to load thumbnails for page.");
    } finally {
      setLoading(false);
    }
  };

  // Prefetch thumbnails for up to `count` pages after `page`
  const prefetchNextPages = async (page: number, count = 2) => {
    const idsSource = allIdsRef.current ?? allIds ?? [];
    if (idsSource.length === 0) return;
    const startPage = page + 1;
    const endPage = Math.min(
      Math.ceil(idsSource.length / PAGE_SIZE),
      page + count,
    );
    for (let p = startPage; p <= endPage; p++) {
      const start = (p - 1) * PAGE_SIZE;
      const ids = idsSource.slice(start, start + PAGE_SIZE);
      const toFetch = ids.filter((id) => !thumbCache.current.has(id));
      if (toFetch.length === 0) continue;
      try {
        const results = await fetchThumbnailsForIds(toFetch);
        results.forEach((r) => {
          if (r.url) {
            createdUrls.current.push(r.url);
            thumbCache.current.set(r.id, r.url);
          } else {
            thumbCache.current.set(r.id, undefined);
          }
        });
      } catch (err) {
        // ignore prefetch failures
        // eslint-disable-next-line no-console
        console.debug("prefetch failed", err);
      }
    }
  };

  // compute pagination info
  const loadedPages = Math.max(
    1,
    Math.ceil((allIds ? allIds.length : items.length) / PAGE_SIZE),
  );
  const speciesTotalImages =
    specimenData?.imageCounts ?? (allIds ? allIds.length : items.length);
  // show true species total pages (don't cap here) so pagination reflects full dataset
  const speciesTotalPages = Math.max(
    1,
    Math.ceil(speciesTotalImages / PAGE_SIZE),
  );
  // totalPages represents the number of pages currently loaded (not full species)
  const totalPages = loadedPages;

  const gotoPage = (p: number) => {
    if (!allIds) return;
    // The shared pagination control has no in-flight state of its own, so the
    // re-entrancy guard lives here.
    if (isLoadingMore || loading) return;
    const requested = Math.max(1, p);

    // compute currently loaded pages from available ids
    const currentLoadedPages = Math.max(
      1,
      Math.ceil((allIds ? allIds.length : items.length) / PAGE_SIZE),
    );

    // If the requested page is already loaded, show it immediately.
    if (requested <= currentLoadedPages) {
      if (requested === currentPage) return; // already viewing
      // displayPage gives immediate feedback; actual commit happens in loadPage
      setDisplayPage(requested);
      setLoading(true);
      setError(null);
      loadPage(requested);
      return;
    }

    // When requesting a page beyond what's currently loaded, avoid jumping
    // the pagination window too far. Show the next available page (loaded
    // pages + 1) immediately as a placeholder so the pagination shifts only
    // one step to the right instead of leaping to `requested`.
    const immediate = Math.min(requested, currentLoadedPages + 1);
    setDisplayPage(immediate);
    setLoading(true);
    setError(null);


    // otherwise, we need to load additional chunks until we have enough ids
    const neededCount = requested * PAGE_SIZE;
    const ensureIdsAndLoad = async () => {
      // Try to fetch the remaining IDs in a single request instead of looping
      // to reduce round trips and avoid races.
      const existing = allIdsRef.current ? allIdsRef.current : [];
      let remaining = neededCount - existing.length;
      if (remaining > 0 && speciesName) {
        setIsLoadingMore(true);
        try {
          const fetched = await fetchSpeciesImageIds(
            speciesName,
            remaining,
            existing.length,
          );
          if (!fetched || fetched.length === 0) {
            setExhaustedIds(true);
          } else {
            const deduped = fetched.filter((id) => !existing.includes(id));
            if (deduped.length > 0) {
              const newAll = [...existing, ...deduped];
              setAllIds(newAll);
              allIdsRef.current = newAll;
            } else {
              // no progress -> mark exhausted to avoid infinite retries
              setExhaustedIds(true);
            }
          }
        } catch (err) {
          console.error("Error fetching IDs for jump:", err);
        } finally {
          setIsLoadingMore(false);
        }
      }

      // after fetching, compute the page we can actually show (cap to available pages)
      const availablePages = Math.max(
        1,
        Math.ceil(
          (allIdsRef.current ? allIdsRef.current.length : 0) / PAGE_SIZE,
        ),
      );
      const toShow = Math.min(requested, availablePages);
      // Ensure we load the page that actually exists now (may be less than requested if exhausted)
      await loadPage(toShow);
    };
    void ensureIdsAndLoad();
  };

  // NOTE: We intentionally do not short-circuit render while `loading` is true
  // because that caused a full-page layout shift. Instead we keep the header,
  // pagination and grid in place and show per-tile placeholders while images
  // load. This makes navigation feel stable and less janky.
  if (error) return <div className="py-4 text-burnt-peach-600">{error}</div>;

  // Ids for the currently displayed grid page (or preview), used to drive
  // the shared full-image modal's prev/next navigation. Mirrors the id list
  // each grid-rendering branch below computes for its own tiles.
  const modalPageIds = showAll
    ? allIds
      ? allIds.slice(
          (displayPage - 1) * PAGE_SIZE,
          (displayPage - 1) * PAGE_SIZE + PAGE_SIZE,
        )
      : items.map((it) => it.id)
    : allIds
      ? allIds.slice(0, MAX_PREVIEW)
      : items.map((it) => it.id).slice(0, MAX_PREVIEW);

  return (
    <div>
      {/* Specimen header (icon + image count) */}
      {showImageCount && (
        <div className="flex items-center gap-4 mb-8">
          <IconContainer>
            <ButterflyComplex className="w-16 h-16 fill-pacific-blue-500" />
          </IconContainer>
          <div className="my-2">
            {specimenLoading ? (
              <ImageLoading size={72} msg={"Loading image count"} />
            ) : specimenData ? (
              <>
                <p className="text-sm text-deep-mocha-500">Image count</p>
                <p className="text-xl font-semibold">
                  {formatNumberToLocaleString(specimenData.imageCounts)}
                </p>
              </>
            ) : (
              <p className="text-sm text-deep-mocha-500">
                Image count unavailable
              </p>
            )}
          </div>
        </div>
      )}
      {showUmap && (
        <div
          id="specimen-umap"
          className={`transition-opacity duration-200 ${openIndexInPage !== null ? "opacity-30 pointer-events-none" : "opacity-100"}`}
        >
          <ImageUmap species={speciesName ?? ""} />
        </div>
      )}
      <div id="specimen-thumbs" className="mt-8">
        {!showAll && (
          <h2 className="text-xl font-medium text-deep-mocha-700 dark:text-deep-mocha-300 mb-3">
            Specimen Images
          </h2>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3 mb-6">
          {/* Render a stable grid for the current page using thumbCache to avoid
              layout shift. If a thumbnail isn't available yet, show the
              placeholder but keep the tile size fixed so the page doesn't jump. */}
          {(() => {
            // If we're showing a preview (not full gallery), render only two rows (16 images)
            if (!showAll) {
              const MAX_PREVIEW = 16;
              const pageIds = allIds
                ? allIds.slice(0, MAX_PREVIEW)
                : items.map((it) => it.id).slice(0, MAX_PREVIEW);
              const renderIds =
                pageIds.length > 0
                  ? pageIds
                  : Array.from({ length: MAX_PREVIEW }).map(
                      (_, i) => `ph-${i}`,
                    );

              return renderIds.map((idOrPlaceholder) => {
                const isPlaceholder =
                  typeof idOrPlaceholder !== "string" ||
                  idOrPlaceholder.startsWith("ph-");
                const id = isPlaceholder ? undefined : idOrPlaceholder;
                const cached = id ? thumbCache.current.get(id) : undefined;
                const isLoaded = id ? loadedThumbIds.has(id) : false;

                return (
                  <button
                    key={id ?? String(idOrPlaceholder)}
                    onClick={() => {
                      if (!id) return;
                      const idx = pageIds.indexOf(id);
                      if (idx >= 0) setOpenIndexInPage(idx);
                    }}
                    title={id ? "Open full image" : undefined}
                    className="relative w-full aspect-square rounded-xl overflow-hidden border border-deep-mocha-200 dark:border-deep-mocha-700 transition-all hover:shadow-lg hover:ring-1 hover:ring-pacific-blue-600"
                  >
                    {cached ? (
                      <>
                        <img
                          src={cached}
                          alt={id ? `Specimen ${id}` : "Loading..."}
                          loading="lazy"
                          decoding="async"
                          className="object-contain object-center w-full h-full"
                          onLoad={() => {
                            if (!id) return;
                            setLoadedThumbIds((s) => {
                              if (s.has(id)) return s;
                              const n = new Set(s);
                              n.add(id);
                              return n;
                            });
                          }}
                        />
                        <div
                          className={`absolute inset-0 flex items-center justify-center bg-deep-mocha-100/70 dark:bg-deep-mocha-800/70 transition-opacity ${
                            isLoaded
                              ? "opacity-0 pointer-events-none"
                              : "opacity-100"
                          }`}
                        >
                          <ImageLoading size={110} msg={"Image loading"} />
                        </div>
                      </>
                    ) : (
                      <div className="flex items-center justify-center bg-deep-mocha-100 dark:bg-deep-mocha-800 text-sm text-deep-mocha-400 h-full">
                        <ImageLoading size={110} msg={"Images loading"} />
                      </div>
                    )}
                  </button>
                );
              });
            }

            const start = (displayPage - 1) * PAGE_SIZE;
            const pageIds = allIds
              ? allIds.slice(start, start + PAGE_SIZE)
              : items.map((it) => it.id);

            // If there are no ids at all, show PAGE_SIZE placeholders
            const renderIds =
              pageIds.length > 0
                ? pageIds
                : Array.from({ length: PAGE_SIZE }).map((_, i) => `ph-${i}`);

            return renderIds.map((idOrPlaceholder) => {
              const isPlaceholder =
                typeof idOrPlaceholder !== "string" ||
                idOrPlaceholder.startsWith("ph-");
              const id = isPlaceholder ? undefined : idOrPlaceholder;
              const cached = id ? thumbCache.current.get(id) : undefined;

              // For each tile we render the thumbnail (if available) and an
              // overlaying placeholder that remains visible until that tile's
              // image has fired its load event. This ensures each box always
              // shows the loading UI until its specific image is ready.
              const isLoaded = id ? loadedThumbIds.has(id) : false;

              return (
                <button
                  key={id ?? String(idOrPlaceholder)}
                  onClick={() => {
                    if (!id) return;
                    const idx = pageIds.indexOf(id);
                    if (idx >= 0) setOpenIndexInPage(idx);
                  }}
                  title={id ? "Open full image" : undefined}
                  className="relative w-full aspect-square rounded-xl overflow-hidden border border-deep-mocha-200 dark:border-deep-mocha-700 transition-all hover:shadow-lg hover:ring-1 hover:ring-pacific-blue-600"
                >
                  {cached ? (
                    // render the image but keep a placeholder overlay until it loads
                    <>
                      <img
                        src={cached}
                        alt={id ? `Specimen ${id}` : "Loading..."}
                        loading="lazy"
                        decoding="async"
                        className="object-contain object-center w-full h-full"
                        onLoad={() => {
                          if (!id) return;
                          setLoadedThumbIds((s) => {
                            if (s.has(id)) return s;
                            const n = new Set(s);
                            n.add(id);
                            return n;
                          });
                        }}
                      />

                      <div
                        className={`absolute inset-0 flex items-center justify-center bg-deep-mocha-100/70 dark:bg-deep-mocha-800/70 transition-opacity ${
                          isLoaded
                            ? "opacity-0 pointer-events-none"
                            : "opacity-100"
                        }`}
                      >
                        <ImageLoading size={110} msg={"Images loading"} />
                      </div>
                    </>
                  ) : (
                    <div className="flex items-center justify-center bg-deep-mocha-100 dark:bg-deep-mocha-800 text-sm text-deep-mocha-400 h-full">
                      <ImageLoading size={110} msg={"Images loading"} />
                    </div>
                  )}
                </button>
              );
            });
          })()}
        </div>
      </div>
      {/* If we're showing only a preview, render a "View more images" button when more images exist */}
      {!showAll && speciesTotalImages > 16 && nameOr(speciesName) && (
        <div className="flex items-center justify-center mt-4">
          <a
            href={`/species/${encodeURIComponent(nameOr(speciesName))}/gallery`}
            target="_blank"
            rel="noopener noreferrer"
            className={`h-9 flex items-center px-5 rounded-full text-sm font-medium transition-all bg-gradient-to-r from-hunter-green-500 via-pacific-blue-500 to-frozen-water-500 text-white shadow hover:opacity-90 hover:shadow-md`}
          >
            View more images
          </a>
        </div>
      )}

      {/* Pagination bar (shared with the text search results) */}
      {showAll && (
        <PaginationControls
          currentPage={displayPage}
          totalPages={speciesTotalPages}
          totalItems={speciesTotalImages}
          itemsPerPage={PAGE_SIZE}
          label="images"
          onPageChange={gotoPage}
        />
      )}

      {/* Modal/lightbox for full-size image */}
      <SpecimenImageModal
        ids={modalPageIds}
        openIndex={openIndexInPage}
        onOpenIndexChange={setOpenIndexInPage}
      />

    </div>
  );
};

export default SpecimensTab;
