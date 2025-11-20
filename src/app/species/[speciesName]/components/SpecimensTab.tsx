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
  fetchImgById,
  fetchSpeciesImageIds,
} from "@/lib/images";

interface SpecimensTabProps {
  // keep backward compatibility: callers may pass specimens array
  specimens?: any[] | undefined;
  // preferred: pass speciesName to fetch image IDs from backend
  speciesName?: string;
}

type ThumbItem = {
  id: string;
  thumbUrl?: string;
};

const SpecimensTab: React.FC<SpecimensTabProps> = ({ specimens, speciesName }) => {
  const [items, setItems] = useState<ThumbItem[]>([]); // current page items
  const [specimenData, setSpecimenData] = useState<SpecimenData | null>(null);
  const [specimenLoading, setSpecimenLoading] = useState(false);
  const [allIds, setAllIds] = useState<string[] | null>(null); // all image ids for species
  const allIdsRef = useRef<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const createdUrls = useRef<string[]>([]);
  // pagination
  const PAGE_SIZE = 24; // images per page
  const MAX_PAGES = 10; // show up to 10 pages
  const INITIAL_PAGES = 5; // initial pages to request (24 * 5 = 120)
  const [currentPage, setCurrentPage] = useState<number>(1); // 1-based
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);
  const [exhaustedIds, setExhaustedIds] = useState<boolean>(false);
  const [hasLoadedExtra, setHasLoadedExtra] = useState<boolean>(false);

  // simple cache of fetched thumbnail URLs by image id
  const thumbCache = useRef<Map<string, string | undefined>>(new Map());
  // cache for fetched full-size images while modal is open
  const fullCache = useRef<Map<string, string>>(new Map());

    // moved logic into named helpers below and call them here
    useEffect(() => {
    let mountedMeta = true;
    let mounted = true;

    const run = async () => {
      await loadMeta(speciesName, mountedMeta);

      if (!mounted) return;

      if (speciesName) {
        await loadFromSpecies(nameOr(speciesName), mounted);
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
  }, [speciesName, specimens]);

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
    fullCache.current.forEach((u) => {
      try {
        URL.revokeObjectURL(u);
      } catch {
        /* ignore */
      }
    });
    fullCache.current.clear();
  }

  // fetch a list of thumbnails for given ids (defensive: returns url undefined on failure)
  async function fetchThumbnailsForIds(ids: string[]) {
    const promises = ids.map((id) =>
      fetchThumbnailById(id)
        .then((url) => ({ id, url }))
        .catch(() => ({ id, url: undefined }))
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
    setExhaustedIds(false);
    setHasLoadedExtra(false);

    try {
      const initialLimit = PAGE_SIZE * INITIAL_PAGES; // 24 * 5 = 120
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
      if (specimenData?.imageCounts && ids.length >= specimenData.imageCounts) setExhaustedIds(true);
      const toUse = ids.slice(0, PAGE_SIZE);
      const results = await fetchThumbnailsForIds(toUse);
      if (!mountedFlag) return;
      results.forEach((r) => {
        thumbCache.current.set(r.id, r.url);
      });
      setItems(results.map((r) => ({ id: r.id, thumbUrl: r.url })));
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
      const fetched = await fetchSpeciesImageIds(speciesName, PAGE_SIZE, offset);
      // if backend returns fewer than requested, we've exhausted available ids
      if (!fetched || fetched.length === 0) {
        setExhaustedIds(true);
        return;
      }

      // determine deduped additions and new full list
      const deduped = fetched.filter((id) => !existing.includes(id));
      const newAll = [...existing, ...deduped];
      // update state with the new list (use functional set to avoid race)
      setAllIds(newAll);
      allIdsRef.current = newAll;
      // mark that we've appended extra pages beyond the initial load
      if (offset > 0 && deduped.length > 0) setHasLoadedExtra(true);

      // compute the page index of the first newly added item using the previous length
      const firstNewIndex = existing.length;
      const firstNewPage = Math.floor(firstNewIndex / PAGE_SIZE) + 1;
      setCurrentPage(firstNewPage);
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
  async function loadFromSpecimensFallback(specimensArr: any[], mountedFlag = true) {
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
      if (mountedFlag) setItems(results.map((r) => ({ id: r.id, thumbUrl: r.url })));
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
    if (!allIds) return;
    const total = allIds.length;
    const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const p = Math.max(1, Math.min(pageCount, page));
    setCurrentPage(p);
    setLoading(true);
    setError(null);

    const start = (p - 1) * PAGE_SIZE;
    const pageIds = allIds.slice(start, start + PAGE_SIZE);

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
    } catch (err) {
      console.error("Failed to load page thumbnails.", err);
      setError("Failed to load thumbnails for page.");
    } finally {
      setLoading(false);
    }
  };

  const openFull = async (id: string) => {
    try {
      setModalError(null);
      // if full image already cached, use it
      if (fullCache.current.has(id)) {
        const cached = fullCache.current.get(id)!;
        setModalImageUrl(cached);
        setModalOpen(true);
        if (allIds) {
          const idx = allIds.indexOf(id);
          setModalIndex(idx >= 0 ? idx : null);
        } else {
          setModalIndex(null);
        }
        // prefetch neighbors
        prefetchNeighbors(id);
        return;
      }

      setModalLoading(true);
      // fetch full image blob URL and cache it
      const url = await fetchImgById(id);
      createdUrls.current.push(url);
      fullCache.current.set(id, url);
      setModalImageUrl(url);
      if (allIds) {
        const idx = allIds.indexOf(id);
        setModalIndex(idx >= 0 ? idx : null);
      } else {
        setModalIndex(null);
      }
      setModalOpen(true);
      // prefetch neighbors
      prefetchNeighbors(id);
    } catch (err) {
      console.error("Failed to open full image:", err);
      setModalError("Failed to load full image.");
    } finally {
      setModalLoading(false);
    }
  };

  // prefetch previous and next full images to reduce loading latency
  const prefetchNeighbors = (id: string) => {
    if (!allIds) return;
    const idx = allIds.indexOf(id);
    if (idx < 0) return;
    const neighbors = [idx - 1, idx + 1];
    neighbors.forEach((n) => {
      if (n < 0 || n >= allIds.length) return;
      const nid = allIds[n];
      if (fullCache.current.has(nid)) return; // already cached
      // fetch but don't block UI
      fetchImgById(nid)
        .then((url) => {
          createdUrls.current.push(url);
          fullCache.current.set(nid, url);
        })
        .catch(() => {
          // ignore prefetch failures
        });
    });
  };

  // modal state for full-size image viewer
  const [modalOpen, setModalOpen] = useState(false);
  const [modalImageUrl, setModalImageUrl] = useState<string | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [modalIndex, setModalIndex] = useState<number | null>(null); // index into allIds

  const revokeUrl = (url?: string | null) => {
    if (!url) return;
    try {
      URL.revokeObjectURL(url);
    } catch {
      /* ignore */
    }
    // remove from createdUrls list if present
    createdUrls.current = createdUrls.current.filter((u) => u !== url);
    // also remove from fullCache if present
    for (const [k, v] of Array.from(fullCache.current.entries())) {
      if (v === url) fullCache.current.delete(k);
    }
  };

  const closeModal = () => {
    if (modalImageUrl) {
      // revoke and remove
      revokeUrl(modalImageUrl);
    }
    // revoke any prefetched full images too
    fullCache.current.forEach((u) => {
      try {
        URL.revokeObjectURL(u);
      } catch {
        /* ignore */
      }
    });
    fullCache.current.clear();
    setModalImageUrl(null);
    setModalOpen(false);
    setModalError(null);
    setModalLoading(false);
    setModalIndex(null);
  };

  // close on ESC
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && modalOpen) closeModal();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalOpen, modalImageUrl]);

  // keyboard left/right navigation
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!modalOpen || modalIndex == null || !allIds) return;
        if (e.key === "ArrowLeft") {
        if (modalIndex > 0) navigateModalTo(modalIndex - 1);
      } else if (e.key === "ArrowRight") {
        if (modalIndex < (allIds || []).length - 1) navigateModalTo(modalIndex + 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalOpen, modalIndex, allIds]);

  // navigate modal to index
  const navigateModalTo = async (newIndex: number) => {
    if (!allIds) return;
    const cappedTotal = allIds.length;
    if (newIndex < 0 || newIndex >= cappedTotal) return;
    const id = allIds[newIndex];
    // if cached, use it immediately
    const cached = fullCache.current.get(id);
    if (cached) {
      // set image immediately from cache
      setModalImageUrl(cached);
      setModalIndex(newIndex);
      // ensure modal is open
      setModalOpen(true);
      // prefetch neighbors
      prefetchNeighbors(id);
      return;
    }

    try {
      setModalLoading(true);
      setModalError(null);
      const url = await fetchImgById(id);
      // cache and keep previous image displayed until we swap
      fullCache.current.set(id, url);
      createdUrls.current.push(url);
      // now swap to new image
      if (modalImageUrl) revokeUrl(modalImageUrl);
      setModalImageUrl(url);
      setModalIndex(newIndex);
      // prefetch neighbors
      prefetchNeighbors(id);
    } catch (err) {
      console.error("Failed to navigate to image:", err);
      setModalError("Failed to load image.");
    } finally {
      setModalLoading(false);
    }
  };

  // compute pagination info
  const loadedPages = Math.max(1, Math.ceil((allIds ? allIds.length : items.length) / PAGE_SIZE));
  const speciesTotalImages = specimenData?.imageCounts ?? (allIds ? allIds.length : items.length);
  // show true species total pages (don't cap here) so pagination reflects full dataset
  const speciesTotalPages = Math.max(1, Math.ceil(speciesTotalImages / PAGE_SIZE));
  // totalPages represents the number of pages currently loaded (not full species)
  const totalPages = loadedPages;

  const gotoPage = (p: number) => {
    if (!allIds) return;
    const requested = Math.max(1, p);

    // compute currently loaded pages from available ids
    const currentLoadedPages = Math.max(1, Math.ceil((allIds ? allIds.length : items.length) / PAGE_SIZE));

    // if the requested page is already loaded, just load it
    if (requested <= currentLoadedPages) {
      if (requested === currentPage) return;
      loadPage(requested);
      return;
    }

    // otherwise, we need to load additional chunks until we have enough ids
    const neededCount = requested * PAGE_SIZE;
    const ensureIdsAndLoad = async () => {
      // keep requesting chunks until we have enough or the backend reports exhaustion
      while ((allIdsRef.current ? allIdsRef.current.length : 0) < neededCount && !exhaustedIds) {
        // eslint-disable-next-line no-await-in-loop
        await loadNextChunk();
      }
      // after loading, compute the page we can actually show (cap to available pages)
      const availablePages = Math.max(1, Math.ceil((allIdsRef.current ? allIdsRef.current.length : 0) / PAGE_SIZE));
      const toShow = Math.min(requested, availablePages);
      loadPage(toShow);
    };
    void ensureIdsAndLoad();
  };

  if (loading)
    return (
      <div className="py-6">
        <div className="flex flex-col items-center gap-4">
          <div className="text-gray-500 text-sm flex items-center gap-2">
            <span>Loading specimens</span>
            <span className="flex items-center justify-center gap-1">
              <span className="-ml-1 w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:0ms]" />
              <span className="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:150ms]" />
              <span className="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:300ms]" />
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3 w-full">
            {Array.from({ length: PAGE_SIZE }).map((_, i) => (
              <div
                key={`ph-${i}`}
                className="relative w-full aspect-square rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40 flex items-center justify-center"
              >
                <Image
                  src="/leaflet/images/butterfly.svg"
                  alt="Loading..."
                  width={128}
                  height={128}
                  className="animate-pulse mx-auto"
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  if (error) return <div className="py-4 text-red-600">{error}</div>;
  if (!items || items.length === 0)
    return <p className="text-gray-700">No specimen thumbnails available.</p>;

  return (
    <div>
      {/* Specimen header (icon + image count) */}
      <div className="flex items-center gap-4 mb-4">
        <IconContainer>
          <ButterflyComplex className="w-10 h-10 fill-teal-500" />
        </IconContainer>
        <div className="my-2">
          {specimenLoading ? (
            <ImageLoading size={72} />
          ) : specimenData ? (
            <>
              <p className="text-sm text-gray-500">Image count</p>
              <p className="text-xl font-semibold">
                {formatNumberToLocaleString(specimenData.imageCounts)}
              </p>
            </>
          ) : (
            <p className="text-sm text-gray-500">Image count unavailable</p>
          )}
        </div>
      </div>
      <div id="specimen-thumbs" className="mt-8">
        <h2 className="text-xl font-medium text-gray-700 dark:text-gray-300 mb-3">Specimen Images</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3 mb-4">
          {items.map((it) => (
            <button
              key={it.id}
              onClick={() => openFull(it.id)}
              title="Open full image"
              className="relative w-full aspect-square rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 transition-all hover:shadow-lg hover:ring-1 hover:ring-teal-600"
            >
              {it.thumbUrl ? (
                <Image
                  src={it.thumbUrl}
                  alt={`Specimen ${it.id}`}
                  fill
                  sizes="(max-width:768px) 33vw, 150px"
                  className="object-cover"
                />
              ) : (
                <div className="flex items-center justify-center bg-gray-100 dark:bg-gray-800 text-sm text-gray-500 h-full">
                  <Image
                    src="/leaflet/images/butterfly.svg"
                    alt="Loading..."
                    width={112}
                    height={112}
                    className="animate-pulse mx-auto"
                  />
                </div>
              )}
            </button>
          ))}
        </div>
      </div>
      {/* Pagination bar */}
      <div className="flex items-center justify-center gap-3 mt-3">
        {/* Navigation container styled similar to PageTabs: rounded, dark background */}
        <div className="inline-flex items-center rounded-full bg-gray-800/80 p-1">
          <button
            onClick={() => gotoPage(currentPage - 1)}
            disabled={currentPage <= 1}
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
              currentPage <= 1
                ? "text-gray-500 cursor-not-allowed"
                : "text-gray-200 hover:bg-gray-700"
            }`}
          >
            Prev
          </button>

          {(() => {
            const elems: React.ReactNode[] = [];
            const firstCount = Math.min(INITIAL_PAGES, totalPages);

            // render pages 1..firstCount
            for (let p = 1; p <= firstCount; p++) {
              const isCurrent = p === currentPage;
              elems.push(
                <button
                  key={`p-${p}`}
                  onClick={() => gotoPage(p)}
                  className={`px-3 py-1 mx-0.5 rounded-full text-sm font-medium transition-colors ${
                    isCurrent ? "bg-emerald-500 text-white" : "text-gray-200 hover:bg-gray-700"
                  }`}
                  aria-current={isCurrent ? "page" : undefined}
                >
                  {p}
                </button>
              );
            }

            // If the species has more than the initial pages, show ellipsis + last loaded page
            if (speciesTotalPages > INITIAL_PAGES) {
              const lastLoadedPage = totalPages;
              const showEllipsis = lastLoadedPage > firstCount;
              if (showEllipsis) {
                const ellipsisActive = currentPage > firstCount && currentPage < lastLoadedPage;
                elems.push(
                  <span
                    key="ellipsis"
                    aria-hidden
                    className={`px-3 py-1 mx-0.5 rounded-full text-sm font-medium ${
                      ellipsisActive ? "bg-emerald-500 text-white" : "text-gray-300"
                    }`}
                  >
                    ...
                  </span>
                );

                elems.push(
                  <button
                    key={`p-last`}
                    onClick={() => gotoPage(lastLoadedPage)}
                    className={`px-3 py-1 mx-0.5 rounded-full text-sm font-medium transition-colors ${
                      lastLoadedPage === currentPage ? "bg-emerald-500 text-white" : "text-gray-200 hover:bg-gray-700"
                    }`}
                  >
                    {lastLoadedPage}
                  </button>
                );
              }
            }

            return elems;
          })()}

          {/* Load next page control: hide entirely if initial load already exhausted and we never appended extra pages; show non-clickable 'No more images.' if we've appended pages but are now exhausted */}
          {(() => {
            // if we've exhausted ids from the initial request and haven't loaded extra, don't show control at all
            if (exhaustedIds && !hasLoadedExtra) return null;

            // if we've appended extra pages but are now exhausted, show a non-clickable pill
            if (exhaustedIds && hasLoadedExtra) {
              return (
                <span className={`ml-2 px-3 py-1 rounded-full text-sm font-medium text-gray-500`}>
                  No more images.
                </span>
              );
            }

            // otherwise show the actionable Load next page button
            return (
              <button
                onClick={() => loadNextChunk()}
                disabled={isLoadingMore}
                className={`ml-2 px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                  isLoadingMore ? "text-gray-500 cursor-not-allowed" : "text-gray-200 hover:bg-gray-700 bg-gray-700/20"
                }`}
              >
                {isLoadingMore ? "Loading..." : "Load next page"}
              </button>
            );
          })()}

          <button
            onClick={() => gotoPage(currentPage + 1)}
            disabled={currentPage >= totalPages}
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
              currentPage >= totalPages
                ? "text-gray-500 cursor-not-allowed"
                : "text-gray-200 hover:bg-gray-700"
            }`}
          >
            Next
          </button>
        </div>
      </div>

      {/* Modal/lightbox for full-size image */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          role="dialog"
          aria-modal="true"
          onClick={(e) => {
            // close when clicking on backdrop
            if (e.target === e.currentTarget) closeModal();
          }}
        >
          <div className="relative w-[30vw] max-w-[65vw] max-h-[100vh] flex items-center justify-center">
            {/* left nav */}
            <button
              onClick={() =>
                modalIndex != null ? navigateModalTo(modalIndex - 1) : null
              }
              disabled={modalIndex == null || modalIndex <= 0}
              aria-label="Previous image"
              className={`absolute left-[-48px] z-30 rounded-full p-2 transition-colors ${
                modalIndex == null || modalIndex <= 0
                  ? "text-gray-400 cursor-not-allowed"
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

            <button
              onClick={closeModal}
              aria-label="Close full image"
              className="absolute -top-3 -right-3 z-40 flex items-center justify-center 
                rounded-full p-2 bg-emerald-500 hover:bg-emerald-400 
                dark:bg-emerald-600 dark:hover:bg-emerald-500 
                text-gray border border-white/50 shadow-md hover:shadow-lg 
                transition-all duration-200"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 text-gray-700"
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

            {/* Formatting of popout image box (keep your colors/borders but reserve a fixed box to prevent resizing) */}
            <div className="bg-gray-100 dark:bg-gray-900 border border-gray-500 dark:border-gray-600 rounded-lg p-4 w-full h-full flex items-center justify-center">
              {modalLoading ? (
                // Loading placeholder occupies the same space as the final image to avoid layout jumps
                <div className="w-full h-full flex items-center justify-center">
                  <div className="w-full h-full flex items-center justify-center max-w-full max-h-full">
                    <ImageLoading size={200} />
                  </div>
                </div>
              ) : modalImageUrl ? (
                // use native img for blob URLs; constrain to the container so the box doesn't resize
                <img
                  src={modalImageUrl}
                  alt="Full size specimen"
                  className="max-h-full max-w-full object-contain rounded-lg"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-700">
                  {modalError ?? "Unable to load image"}
                </div>
              )}
            </div>

            {/* right nav */}
            <button
              onClick={() =>
                modalIndex != null ? navigateModalTo(modalIndex + 1) : null
              }
              disabled={
                modalIndex == null ||
                modalIndex >= (allIds || []).length - 1
              }
              aria-label="Next image"
              className={`absolute right-[-48px] z-30 rounded-full p-2 transition-colors ${
                modalIndex == null || modalIndex >= (allIds || []).length - 1
                  ? "text-gray-400 cursor-not-allowed"
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
        </div>
      )}
    </div>
  );
};

export default SpecimensTab;
