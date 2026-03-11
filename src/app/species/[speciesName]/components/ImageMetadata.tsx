"use client";
import React, { useEffect, useState } from "react";
import { NoData } from "@/components/NoData";

interface ImageMetadataProps {
  speciesName?: string;
  imageId?: string | null;
}

export default function ImageMetadata({ speciesName, imageId }: ImageMetadataProps) {
  const [meta, setMeta] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!imageId) {
      setMeta(null);
      setLoading(false);
      return;
    }

    let ignore = false;
    const fetchMeta = async () => {
      try {
        setMeta(null);
        setLoading(true);
        const res = await fetch(`/api/images/id/metadata?imageId=${encodeURIComponent(imageId)}`);
        if (!res.ok) {
          const txt = await res.text().catch(() => "");
          console.debug("Failed to fetch image metadata", res.status, txt);
          if (!ignore) setLoading(false);
          return;
        }
        const data = await res.json();
        if (!ignore) setMeta(data ?? null);
      } catch (err) {
        console.error("Error fetching image metadata:", err);
      } finally {
        if (!ignore) setLoading(false);
      }
    };

    void fetchMeta();
    return () => {
      ignore = true;
    };
  }, [imageId]);

  return (
    <div className="p-4 bg-gray-100 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl text-xs text-gray-800 dark:text-white">
      <h2 className="text-lg font-semibold mb-2">Image Metadata</h2>
      <div className="flex flex-col gap-2">
        {loading ? (
          <div className="text-center text-sm text-gray-500">Loading metadata…</div>
        ) : !meta ? (
          <NoData text={imageId ? "No metadata available." : "No image selected."} />
        ) : (
          <>
            {meta.class_dv && (
              <div>
                <span className="font-medium text-emerald-700 dark:text-emerald-500">View: </span>
                <span className="text-gray-700 dark:text-white">{typeof meta.class_dv === 'string' ? meta.class_dv.charAt(0).toUpperCase() + meta.class_dv.slice(1) : meta.class_dv}</span>
              </div>
            )}

            {(meta.lat || meta.lon) && (
              <div>
                <span className="font-medium text-emerald-700 dark:text-emerald-500">Location: </span>
                <span className="text-gray-700 dark:text-white">{meta.lat ?? "—"}, {meta.lon ?? "—"}</span>
              </div>
            )}

            {meta.source_db && (
              <div>
                <span className="font-medium text-emerald-700 dark:text-emerald-500">Source DB: </span>
                <span className="text-gray-700 dark:text-white">{typeof meta.source_db === 'string' ? meta.source_db.charAt(0).toUpperCase() + meta.source_db.slice(1) : meta.source_db}</span>
              </div>
            )}

            <div className="mt-3 flex flex-wrap gap-2 justify-center">
              {typeof meta.license === "string" && meta.license.startsWith("http") && (
                <a
                  href={meta.license}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-900"
                  aria-label="Open license"
                >
                  License
                </a>
              )}
              {meta.uuid && (
                <a
                  href={meta.uuid}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-900"
                  aria-label="Open source link"
                >
                  Source Link
                </a>
              )}
              {meta.uri && (
                <a
                  href={meta.uri}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-900"
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
  );
}
