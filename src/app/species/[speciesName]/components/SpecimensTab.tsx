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
import ImageUmap from "./ImageUmap";
import Tips from "@/components/Tips";
import GalleryPagination from "./GalleryPagination";

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

const SpecimensTab: React.FC<SpecimensTabProps> = ({ specimens, speciesName, showAll: propsShowAll, showUmap: propsShowUmap, showImageCount: propsShowImageCount, initialSpecimenData }) => {
  const [items, setItems] = useState<ThumbItem[]>([]); // current page items
  // initialize specimen metadata from optional prop to avoid re-fetching
  const [specimenData, setSpecimenData] = useState<SpecimenData | null>(initialSpecimenData ?? null);
  const [specimenLoading, setSpecimenLoading] = useState(false);
  const [allIds, setAllIds] = useState<string[] | null>(null); // all image ids for species
  const allIdsRef = useRef<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const createdUrls = useRef<string[]>([]);
  // pagination
  const PAGE_SIZE = 24; // images per page
  const INITIAL_PAGES = 5; // initial pages to request (24 * 5 = 120)
  // preview size for species overview (two rows)
  const MAX_PREVIEW = 16;
  const [currentPage, setCurrentPage] = useState<number>(1); // 1-based
  // `displayPage` is the visual page highlighted in the UI. We update it
  // immediately on user actions to provide instant feedback; `currentPage`
  // represents the committed page once data has been loaded.
  const [displayPage, setDisplayPage] = useState<number>(1);
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);
  const [exhaustedIds, setExhaustedIds] = useState<boolean>(false);
  // stable highlighted page in the pagination UI to avoid flashing.
  const [highlightPage, setHighlightPage] = useState<number>(1);

  // simple cache of fetched thumbnail URLs by image id
  const thumbCache = useRef<Map<string, string | undefined>>(new Map());
  const showAll = propsShowAll ?? false;
  const showUmap = propsShowUmap ?? true;
  const showImageCount = propsShowImageCount ?? true;
  // track which thumbnails have finished loading (by id)
  const [loadedThumbIds, setLoadedThumbIds] = useState<Set<string>>(new Set());
  // cache for fetched full-size images while modal is open
  const fullCache = useRef<Map<string, string>>(new Map());

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
      if (specimenData?.imageCounts && ids.length >= specimenData.imageCounts) setExhaustedIds(true);
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
    setDisplayPage(1);
    setExhaustedIds(false);

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
      // prefetch next two pages after initial load
      void prefetchNextPages(1, 2);
      // initialize stable highlight for pagination
      {
        const total = ids.length;
        const displayTotal = Math.max(1, Math.ceil(total / PAGE_SIZE));
        const windowSize = 10;
        const half = Math.floor(windowSize / 2);
        const p = 1;
        const inMiddleRange = p > half && p <= displayTotal - half;
        const newHighlight = inMiddleRange ? Math.max(1, 1 - half) + half : p;
        setHighlightPage(newHighlight);
      }
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
      // sync display/committed page
      setCurrentPage(1);
      setDisplayPage(1);
      // initialize stable highlight for pagination
      {
        const total = idsFromSpecimens.length;
        const displayTotal = Math.max(1, Math.ceil(total / PAGE_SIZE));
        const windowSize = 10;
        const half = Math.floor(windowSize / 2);
        const p = 1;
        const inMiddleRange = p > half && p <= displayTotal - half;
        const newHighlight = inMiddleRange ? Math.max(1, p - half) + half : p;
        setHighlightPage(newHighlight);
      }
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
      // update the stable highlight so the pagination doesn't flash.
      const total = allIdsRef.current ? allIdsRef.current.length : items.length;
      const displayTotal = Math.max(1, Math.ceil(total / PAGE_SIZE));
      const windowSize = 10;
      const half = Math.floor(windowSize / 2);
      let start = p - half;
      if (start < 1) start = 1;
      let end = start + windowSize - 1;
      if (end > displayTotal) {
        end = displayTotal;
        start = Math.max(1, end - windowSize + 1);
      }
      const inMiddleRange = p > half && p <= displayTotal - half;
      const newHighlight = inMiddleRange ? start + half : p;
      setHighlightPage(newHighlight);
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
    const endPage = Math.min(Math.ceil(idsSource.length / PAGE_SIZE), page + count);
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

  const openFull = async (id: string) => {
    try {
      setModalError(null);
      // if full image already cached, use it
      if (fullCache.current.has(id)) {
        const cached = fullCache.current.get(id)!;
        setModalImageUrl(cached);
        setModalOpen(true);
        // fetch metadata for cached image
        void fetchAndSetModalMeta(id);
        if (allIds) {
          const idx = allIds.indexOf(id);
          setModalIndex(idx >= 0 ? idx : null);
          // limit modal navigation to the currently displayed page
          const pageStart = (displayPage - 1) * PAGE_SIZE;
          const pageEnd = Math.min(allIds.length - 1, pageStart + PAGE_SIZE - 1);
          setModalPageRange({ start: pageStart, end: pageEnd });
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
      // fetch metadata for this image
      void fetchAndSetModalMeta(id);
      if (allIds) {
        const idx = allIds.indexOf(id);
        setModalIndex(idx >= 0 ? idx : null);
        const pageStart = (displayPage - 1) * PAGE_SIZE;
        const pageEnd = Math.min(allIds.length - 1, pageStart + PAGE_SIZE - 1);
        setModalPageRange({ start: pageStart, end: pageEnd });
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

  // metadata for currently shown modal image
  const [modalMeta, setModalMeta] = useState<any | null>(null);

  const fetchAndSetModalMeta = async (id: string) => {
    try {
      setModalMeta(null);
      const res = await fetch(`/api/images/id/metadata?imageId=${encodeURIComponent(id)}`);
      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        console.debug("Failed to fetch image metadata", res.status, txt);
        return;
      }
      const data = await res.json();
      setModalMeta(data ?? null);
    } catch (err) {
      console.error("Error fetching image metadata:", err);
    }
  };

  // modal state for full-size image viewer
  const [modalOpen, setModalOpen] = useState(false);
  const [modalImageUrl, setModalImageUrl] = useState<string | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [modalIndex, setModalIndex] = useState<number | null>(null); // index into allIds
  // modal navigation limited to the currently displayed page's index range
  const [modalPageRange, setModalPageRange] = useState<{ start: number; end: number } | null>(null);

  // prevent background scrolling when the modal is open; restore previous overflow on close
  const originalBodyOverflow = useRef<string | null>(null);
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (modalOpen) {
      originalBodyOverflow.current = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    } else if (originalBodyOverflow.current !== null) {
      document.body.style.overflow = originalBodyOverflow.current;
      originalBodyOverflow.current = null;
    }

    return () => {
      if (originalBodyOverflow.current !== null) {
        document.body.style.overflow = originalBodyOverflow.current;
        originalBodyOverflow.current = null;
      }
    };
  }, [modalOpen]);

  // keep modal page range in sync when modal/displayPage/allIds change
  useEffect(() => {
    if (!modalOpen || !allIds) {
      setModalPageRange(null);
      return;
    }
    const pageStart = (displayPage - 1) * PAGE_SIZE;
    const pageEnd = Math.min(allIds.length - 1, pageStart + PAGE_SIZE - 1);
    setModalPageRange({ start: pageStart, end: pageEnd });
  }, [modalOpen, displayPage, allIds]);

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
    setModalMeta(null);
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
    // prevent navigating outside the currently displayed page range
    if (modalPageRange) {
      if (newIndex < modalPageRange.start || newIndex > modalPageRange.end) return;
    }
    const id = allIds[newIndex];
    // if cached, use it immediately
    const cached = fullCache.current.get(id);
    if (cached) {
      // set image immediately from cache
      setModalImageUrl(cached);
      setModalIndex(newIndex);
      // ensure modal is open
      setModalOpen(true);
      // fetch metadata for this image
      void fetchAndSetModalMeta(id);
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
      // fetch metadata for this image
      void fetchAndSetModalMeta(id);
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

    // If the requested page is already loaded, show it immediately.
    if (requested <= currentLoadedPages) {
      if (requested === currentPage) return; // already viewing
      // displayPage gives immediate feedback; actual commit happens in loadPage
      setDisplayPage(requested);
      // update stable highlight immediately to avoid flashing between
      // the old highlight and the newly requested display page while
      // `loadPage` is still fetching thumbnails.
      {
        const displayTotal = Math.max(1, Math.ceil((specimenData?.imageCounts ?? (allIds ? allIds.length : items.length)) / PAGE_SIZE));
        const windowSize = 10;
        const half = Math.floor(windowSize / 2);
        let start = requested - half;
        if (start < 1) start = 1;
        let end = start + windowSize - 1;
        if (end > displayTotal) {
          end = displayTotal;
          start = Math.max(1, end - windowSize + 1);
        }
        const inMiddleRange = requested > half && requested <= displayTotal - half;
        const newHighlight = inMiddleRange ? start + half : requested;
        setHighlightPage(newHighlight);
      }
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

    // set a stable highlight immediately so the pagination UI doesn't
    // flash between the previous highlight and the newly requested one
    // while additional IDs/thumbnails are being fetched.
    {
      const displayTotal = Math.max(1, Math.ceil((specimenData?.imageCounts ?? (allIds ? allIds.length : items.length)) / PAGE_SIZE));
      const windowSize = 10;
      const half = Math.floor(windowSize / 2);
      // prefer to center the highlight when possible
      let start = requested - half;
      if (start < 1) start = 1;
      let end = start + windowSize - 1;
      if (end > displayTotal) {
        end = displayTotal;
        start = Math.max(1, end - windowSize + 1);
      }
      const inMiddleRange = requested > half && requested <= displayTotal - half;
      const newHighlight = inMiddleRange ? start + half : requested;
      setHighlightPage(newHighlight);
    }

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
          const fetched = await fetchSpeciesImageIds(speciesName, remaining, existing.length);
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
      const availablePages = Math.max(1, Math.ceil((allIdsRef.current ? allIdsRef.current.length : 0) / PAGE_SIZE));
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
  if (error) return <div className="py-4 text-red-600">{error}</div>;

  return (
    <div>
      {/* Specimen header (icon + image count) */}
      {showImageCount && (
        <div className="flex items-center gap-4 mb-8">
          <IconContainer>
            <ButterflyComplex className="w-16 h-16 fill-teal-500" />
          </IconContainer>
          <div className="my-2">
            {specimenLoading ? (
              <ImageLoading size={72} msg={"Loading image count"} />
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
      )}
      {showUmap && (
        <div
          id="specimen-umap"
          className={`transition-opacity duration-200 ${modalOpen ? "opacity-30 pointer-events-none" : "opacity-100"}`}
        >
          <ImageUmap species={speciesName ?? ""} />
        </div>
      )}
      <div id="specimen-thumbs" className="mt-8">
        {!showAll && (
          <h2 className="text-xl font-medium text-gray-700 dark:text-gray-300 mb-3">Specimen Images</h2>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3 mb-6">
          {/* Render a stable grid for the current page using thumbCache to avoid
              layout shift. If a thumbnail isn't available yet, show the
              placeholder but keep the tile size fixed so the page doesn't jump. */}
          {(() => {
            // If we're showing a preview (not full gallery), render only two rows (16 images)
            if (!showAll) {
              const MAX_PREVIEW = 16;
              const pageIds = allIds ? allIds.slice(0, MAX_PREVIEW) : items.map((it) => it.id).slice(0, MAX_PREVIEW);
              const renderIds = pageIds.length > 0 ? pageIds : Array.from({ length: MAX_PREVIEW }).map((_, i) => `ph-${i}`);

              return renderIds.map((idOrPlaceholder) => {
                const isPlaceholder = typeof idOrPlaceholder !== "string" || idOrPlaceholder.startsWith("ph-");
                const id = isPlaceholder ? undefined : idOrPlaceholder;
                const cached = id ? thumbCache.current.get(id) : undefined;
                const isLoaded = id ? loadedThumbIds.has(id) : false;

                return (
                  <button
                    key={id ?? String(idOrPlaceholder)}
                    onClick={() => (id ? openFull(id) : undefined)}
                    title={id ? "Open full image" : undefined}
                    className="relative w-full aspect-square rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 transition-all hover:shadow-lg hover:ring-1 hover:ring-teal-600"
                  >
                    {cached ? (
                      <>
                        <img
                          src={cached}
                          alt={id ? `Specimen ${id}` : "Loading..."}
                          className="object-cover w-full h-full"
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
                          className={`absolute inset-0 flex items-center justify-center bg-gray-100/70 dark:bg-gray-800/70 transition-opacity ${
                            isLoaded ? "opacity-0 pointer-events-none" : "opacity-100"
                          }`}
                        >
                          <ImageLoading size={110} msg={"Images loading"} />
                        </div>
                      </>
                    ) : (
                      <div className="flex items-center justify-center bg-gray-100 dark:bg-gray-800 text-sm text-gray-400 h-full">
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
            const renderIds = pageIds.length > 0 ? pageIds : Array.from({ length: PAGE_SIZE }).map((_, i) => `ph-${i}`);

            return renderIds.map((idOrPlaceholder) => {
              const isPlaceholder = typeof idOrPlaceholder !== "string" || idOrPlaceholder.startsWith("ph-");
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
                  onClick={() => (id ? openFull(id) : undefined)}
                  title={id ? "Open full image" : undefined}
                  className="relative w-full aspect-square rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 transition-all hover:shadow-lg hover:ring-1 hover:ring-teal-600"
                >
                  {cached ? (
                    // render the image but keep a placeholder overlay until it loads
                    <>
                      <img
                        src={cached}
                        alt={id ? `Specimen ${id}` : "Loading..."}
                        className="object-cover w-full h-full"
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
                        className={`absolute inset-0 flex items-center justify-center bg-gray-100/70 dark:bg-gray-800/70 transition-opacity ${
                          isLoaded ? "opacity-0 pointer-events-none" : "opacity-100"
                        }`}
                      >
                        <ImageLoading size={110} msg={"Images loading"} />
                      </div>
                    </>
                  ) : (
                    <div className="flex items-center justify-center bg-gray-100 dark:bg-gray-800 text-sm text-gray-400 h-full">
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
            className={`h-9 flex items-center px-5 rounded-full text-sm font-medium transition-all bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-white shadow hover:opacity-90 hover:shadow-md`}
          >
            View more images
          </a>
        </div>
      )}

      {/* Pagination bar (moved to GalleryPagination component) */}
      {showAll && (
        <React.Suspense>
          {/* eslint-disable-next-line @typescript-eslint/ban-ts-comment */}
          {/* @ts-ignore */}
          <GalleryPagination
            displayPage={displayPage}
            gotoPage={gotoPage}
            isLoadingMore={isLoadingMore}
            loading={loading}
            speciesTotalPages={speciesTotalPages}
            highlightPage={highlightPage}
          />
        </React.Suspense>
      )}

      {/* Modal/lightbox for full-size image */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/60"
          role="dialog"
          aria-modal="true"
          onClick={(e) => {
            // close when clicking on backdrop
            if (e.target === e.currentTarget) closeModal();
          }}
        >
          <div className="relative w-[45vw] max-w-[95vw] max-h-[95vh] flex flex-col items-center justify-center gap-4">
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

            {/* Formatting of pop-out image box (keep your colors/borders but reserve a fixed box to prevent resizing) */}
            <div className="bg-gray-100 dark:bg-gray-900 border border-gray-500 dark:border-gray-600 rounded-lg p-4 w-full h-full flex-1 flex items-center justify-center relative">
              {/* left nav (aligned to image) */}
              <button
                onClick={() => (modalIndex != null ? navigateModalTo(modalIndex - 1) : null)}
                disabled={
                  modalIndex == null ||
                  (modalPageRange ? modalIndex <= modalPageRange.start : modalIndex <= 0)
                }
                aria-label="Previous image"
                className={`absolute left-2 top-1/2 z-30 -translate-y-1/2 rounded-full p-2 transition-colors ${
                  (modalIndex == null ||
                    (modalPageRange ? modalIndex <= modalPageRange.start : modalIndex <= 0))
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
              {modalLoading ? (
                // Loading placeholder occupies the same space as the final image to avoid layout jumps
                <div className="w-full h-full flex items-center justify-center">
                  <div className="w-full h-full flex items-center justify-center max-w-full max-h-full">
                    <ImageLoading size={250} />
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
              {/* right nav (aligned to image) */}
              <button
                onClick={() => (modalIndex != null ? navigateModalTo(modalIndex + 1) : null)}
                disabled={
                  modalIndex == null ||
                  (modalPageRange
                    ? modalIndex >= modalPageRange.end
                    : modalIndex >= (allIds || []).length - 1)
                }
                aria-label="Next image"
                className={`absolute right-2 top-1/2 z-30 -translate-y-1/2 rounded-full p-2 transition-colors ${
                  (modalIndex == null ||
                    (modalPageRange
                      ? modalIndex >= modalPageRange.end
                      : modalIndex >= (allIds || []).length - 1))
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
            {/* Metadata box below the image */}
            {modalMeta && (
              <div className="mt-2 w-full max-w-[28vw]">
                <div className="bg-gray-100 dark:bg-gray-900 border border-gray-500 dark:border-gray-600 rounded-2xl p-4 text-xs text-gray-800 dark:text-white">
                  <div className="flex flex-col gap-2">
                    {/* License */}
                    {modalMeta.license && (
                      <div>
                        <span className="font-medium text-emerald-700 dark:text-emerald-500">License: </span>
                        {typeof modalMeta.license === "string" && modalMeta.license.startsWith("http") ? (
                          <a href={modalMeta.license} target="_blank" rel="noopener noreferrer" className="text-black dark:text-white break-words">
                            {modalMeta.license}
                          </a>
                        ) : (
                          <span className="text-gray-700 dark:text-white">{modalMeta.license}</span>
                        )}
                      </div>
                    )}

                    {/* Links (side-by-side): Source & Image */}
                    <div className="flex items-center gap-4">
                      {modalMeta.uuid && (
                        <a
                          href={modalMeta.uuid}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-emerald-700 dark:text-emerald-500 underline"
                        >
                          Source Link
                        </a>
                      )}
                      {modalMeta.uri && (
                        <a
                          href={modalMeta.uri}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-emerald-700 dark:text-emerald-500 underline"
                        >
                          Image Link
                        </a>
                      )}
                    </div>

                    {/* class_dv */}
                    {modalMeta.class_dv && (
                      <div>
                        <span className="font-medium text-emerald-700 dark:text-emerald-500">View: </span>
                        <span className="text-gray-700 dark:text-white">{typeof modalMeta.class_dv === 'string' ? modalMeta.class_dv.charAt(0).toUpperCase() + modalMeta.class_dv.slice(1) : modalMeta.class_dv}</span>
                      </div>
                    )}
                    {/* lat/lon */}
                    {(modalMeta.lat || modalMeta.lon) && (
                      <div>
                        <span className="font-medium text-emerald-700 dark:text-emerald-500">Location: </span>
                        <span className="text-gray-700 dark:text-white">{modalMeta.lat ?? "—"}, {modalMeta.lon ?? "—"}</span>
                      </div>
                    )}
                    {/* source_db */}
                    {modalMeta.source_db && (
                      <div>
                        <span className="font-medium text-emerald-700 dark:text-emerald-500">Source DB: </span>
                        <span className="text-gray-700 dark:text-white">{typeof modalMeta.source_db === 'string' ? modalMeta.source_db.charAt(0).toUpperCase() + modalMeta.source_db.slice(1) : modalMeta.source_db}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* right nav has been moved inside the image container to align vertically with the image */}
          </div>
        </div>
      )}
    </div>
  );
};

export default SpecimensTab;
