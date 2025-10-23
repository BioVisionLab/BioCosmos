"use client";

import React, { useEffect, useRef, useState } from "react";
import Image from "next/image";
import ImageLoading from "@/components/ImageLoading";
import { SpeciesData } from "@/lib/speciesData";
import { fetchThumbnailById, fetchImgById } from "@/lib/speciesList";

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

const TAXON_BASE = "http://127.0.0.1:8000/taxon";

const SpecimensTab: React.FC<SpecimensTabProps> = ({ specimens, speciesName }) => {
  const [items, setItems] = useState<ThumbItem[]>([]); // current page items
  const [allIds, setAllIds] = useState<string[] | null>(null); // all image ids for species
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const createdUrls = useRef<string[]>([]);

  // pagination
  const PAGE_SIZE = 20;
  const MAX_PAGES = 10; // show up to 10 pages
  const [currentPage, setCurrentPage] = useState<number>(1); // 1-based

  // simple cache of fetched thumbnail URLs by image id
  const thumbCache = useRef<Map<string, string | undefined>>(new Map());

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

    const loadFromSpecies = async (name: string) => {
      setLoading(true);
      setError(null);
      setItems([]);
      revokeAll();
      thumbCache.current.clear();
      setAllIds(null);
      setCurrentPage(1);

      try {
        const cleanName = name.toLowerCase().replace(/ /g, "_");
        const res = await fetch(`${TAXON_BASE}/${encodeURIComponent(cleanName)}/ids`);
        if (!mounted) return;

        if (!res.ok) {
          setError("No images found for this species");
          setItems([]);
          return;
        }

        const payload = await res.json();
        let ids: string[] = [];
        if (Array.isArray(payload)) ids = payload as string[];
        else if (payload && Array.isArray(payload.imageIds)) ids = payload.imageIds as string[];

        if (!ids || ids.length === 0) {
          setError("No image IDs returned for this species");
          setItems([]);
          return;
        }

  // store all ids and then load first page
  setAllIds(ids);
  // load thumbnails for page 1
  const toUse = ids.slice(0, PAGE_SIZE);
  const promises = toUse.map((id) => fetchThumbnailById(id).then((url) => ({ id, url })).catch(() => ({ id, url: undefined })));
  const results = await Promise.all(promises);
  if (!mounted) return;
  results.forEach((r) => { if (r.url) createdUrls.current.push(r.url); thumbCache.current.set(r.id, r.url); });
  setItems(results.map((r) => ({ id: r.id, thumbUrl: r.url })));
      } catch (err) {
        console.error("SpecimensTab load error:", err);
        if (mounted) setError("Failed to load specimen thumbnails");
      } finally {
        if (mounted) setLoading(false);
      }
    };

    if (speciesName) {
      loadFromSpecies(speciesName);
    } else if (!speciesName && specimens && specimens.length > 0) {
      // Fallback: if a specimens array was passed, try to use any image IDs present
        const idsFromSpecimens: string[] = (specimens as any[])
        .map((s) => s?.imgId ?? s?.imageId ?? s?.id)
        .filter(Boolean);

      if (idsFromSpecimens.length === 0) {
        // no ids -> render placeholder from specimens as before
        // build simple items with imageUrl if available
        const built: ThumbItem[] = (specimens as any[]).map((s) => ({ id: s?.id ?? s?.catalogNumber ?? Math.random().toString(), thumbUrl: s?.imageUrl }));
        // when specimens have no IDs, treat built items as page 1
        setItems(built.slice(0, PAGE_SIZE));
        setAllIds(built.map((b) => b.id));
      } else {
        // fetch thumbnails for these ids
        setLoading(true);
        setAllIds(idsFromSpecimens);
        // load page 1 thumbnails only
        const pageIds = idsFromSpecimens.slice(0, PAGE_SIZE);
        Promise.all(pageIds.map((id) => fetchThumbnailById(id).then((url) => ({ id, url })).catch(() => ({ id, url: undefined }))))
          .then((results) => {
            results.forEach((r) => { if (r.url) createdUrls.current.push(r.url); thumbCache.current.set(r.id, r.url); });
            if (mounted) setItems(results.map((r) => ({ id: r.id, thumbUrl: r.url })));
          })
          .catch((err) => {
            console.error(err);
            if (mounted) setError("Failed to load thumbnails from specimens");
          })
          .finally(() => { if (mounted) setLoading(false); });
      }
    } else {
      // no speciesName and no specimens
      setItems([]);
    }

    return () => {
      mounted = false;
      revokeAll();
    };
  }, [speciesName, specimens]);

  // helper to load thumbnails for a given page (1-based)
  const loadPage = async (page: number) => {
    if (!allIds) return;
    const total = Math.min(allIds.length, PAGE_SIZE * MAX_PAGES);
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
      return fetchThumbnailById(id).then((url) => ({ id, url })).catch(() => ({ id, url: undefined }));
    });

    try {
      const results = await Promise.all(fetchPromises);
      results.forEach((r) => { if (r.url) { createdUrls.current.push(r.url); thumbCache.current.set(r.id, r.url); } else { thumbCache.current.set(r.id, undefined); } });
      setItems(results.map((r) => ({ id: r.id, thumbUrl: r.url })));
    } catch (err) {
      console.error("Failed to load page thumbnails", err);
      setError("Failed to load thumbnails for page");
    } finally {
      setLoading(false);
    }
  };

  const openFull = async (id: string) => {
    try {
      setModalLoading(true);
      setModalError(null);
      // fetch full image blob URL
      const url = await fetchImgById(id);
      createdUrls.current.push(url);
      setModalImageUrl(url);
      setModalOpen(true);
    } catch (err) {
      console.error("Failed to open full image:", err);
      setModalError("Failed to load full image");
    } finally {
      setModalLoading(false);
    }
  };

  // modal state for full-size image viewer
  const [modalOpen, setModalOpen] = useState(false);
  const [modalImageUrl, setModalImageUrl] = useState<string | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const revokeUrl = (url?: string | null) => {
    if (!url) return;
    try {
      URL.revokeObjectURL(url);
    } catch {
      /* ignore */
    }
    // remove from createdUrls list if present
    createdUrls.current = createdUrls.current.filter((u) => u !== url);
  };

  const closeModal = () => {
    if (modalImageUrl) {
      // revoke and remove
      revokeUrl(modalImageUrl);
    }
    setModalImageUrl(null);
    setModalOpen(false);
    setModalError(null);
    setModalLoading(false);
  };

  // close on ESC
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && modalOpen) closeModal();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalOpen, modalImageUrl]);

  // compute pagination info
  const totalImages = allIds ? Math.min(allIds.length, PAGE_SIZE * MAX_PAGES) : items.length;
  const totalPages = Math.max(1, Math.ceil(totalImages / PAGE_SIZE));

  const gotoPage = (p: number) => {
    if (!allIds) return;
    const clamped = Math.max(1, Math.min(totalPages, p));
    if (clamped === currentPage) return;
    loadPage(clamped);
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

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 w-full">
            {Array.from({ length: PAGE_SIZE }).map((_, i) => (
                  <div
                    key={`ph-${i}`}
                    className="relative w-full aspect-square rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40 flex items-center justify-center"
                  >
                    <Image src="/leaflet/images/butterfly.svg" alt="Loading..." width={96} height={96} className="animate-pulse mx-auto" />
                  </div>
            ))}
          </div>
        </div>
      </div>
    );
  if (error) return <div className="py-4 text-red-600">{error}</div>;
  if (!items || items.length === 0) return <p className="text-gray-700">No specimen thumbnails available.</p>;

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 mb-4">
        {items.map((it) => (
          <button
            key={it.id}
            onClick={() => openFull(it.id)}
            title="Open full image"
            className="relative w-full aspect-square rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 transition-all hover:shadow-lg hover:ring-2 hover:ring-blue-300"
          >
            {it.thumbUrl ? (
              <Image src={it.thumbUrl} alt={`Specimen ${it.id}`} fill sizes="(max-width:768px) 33vw, 150px" className="object-cover" />
            ) : (
              <div className="flex items-center justify-center bg-gray-100 dark:bg-gray-800 text-sm text-gray-500 h-full">
                <Image src="/leaflet/images/butterfly.svg" alt="Loading..." width={64} height={64} className="animate-pulse mx-auto" />
              </div>
            )}
          </button>
        ))}
      </div>

      {/* Pagination bar */}
      <div className="flex items-center justify-center gap-2 mt-2">
        <button
          onClick={() => gotoPage(currentPage - 1)}
          disabled={currentPage <= 1}
          className={`px-3 py-1 rounded ${currentPage <= 1 ? "text-gray-400" : "bg-white/60 hover:bg-gray-200"}`}
        >
          Prev
        </button>

        <nav aria-label="Pages" className="flex items-center gap-1">
          {Array.from({ length: totalPages }).map((_, i) => {
            const p = i + 1;
            return (
              <button
                key={p}
                onClick={() => gotoPage(p)}
                className={`px-3 py-1 rounded ${p === currentPage ? "bg-emerald-500 text-white" : "bg-white/60 hover:bg-gray-200"}`}
                aria-current={p === currentPage ? "page" : undefined}
              >
                {p}
              </button>
            );
          })}
        </nav>

        <button
          onClick={() => gotoPage(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className={`px-3 py-1 rounded ${currentPage >= totalPages ? "text-gray-400" : "bg-white/60 hover:bg-gray-200"}`}
        >
          Next
        </button>
      </div>
      {/* Modal/lightbox for full-size image */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          role="dialog"
          aria-modal="true"
          onClick={(e) => {
            // close when clicking on backdrop
            if (e.target === e.currentTarget) closeModal();
          }}
        >
          <div className="relative max-w-[90vw] max-h-[90vh]">
            <button
              onClick={closeModal}
              aria-label="Close full image"
              className="absolute -top-3 -right-3 z-20 bg-white/90 rounded-full p-2 shadow hover:bg-white"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-700" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 8.586l4.95-4.95a1 1 0 111.414 1.414L11.414 10l4.95 4.95a1 1 0 01-1.414 1.414L10 11.414l-4.95 4.95a1 1 0 01-1.414-1.414L8.586 10 3.636 5.05A1 1 0 015.05 3.636L10 8.586z" clipRule="evenodd" />
              </svg>
            </button>

            <div className="flex items-center justify-center bg-black rounded">
              {modalLoading ? (
                <div className="p-6">
                  <ImageLoading size={200} />
                </div>
              ) : modalImageUrl ? (
                // use native img for blob URLs
                <img src={modalImageUrl} alt="Full size specimen" className="max-h-[80vh] max-w-[90vw] object-contain" />
              ) : (
                <div className="p-6 text-white">{modalError ?? "Unable to load image"}</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SpecimensTab;