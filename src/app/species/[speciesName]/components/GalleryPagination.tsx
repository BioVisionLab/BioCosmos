"use client";

import React from "react";

interface Props {
  displayPage: number;
  gotoPage: (p: number) => void;
  isLoadingMore: boolean;
  loading: boolean;
  speciesTotalPages: number;
  highlightPage: number;
}

export default function GalleryPagination({
  displayPage,
  gotoPage,
  isLoadingMore,
  loading,
  speciesTotalPages,
  highlightPage,
}: Props) {
  return (
    <div className="flex items-center justify-center gap-3 mt-3">
      <button
        onClick={() => gotoPage(displayPage - 1)}
        disabled={displayPage <= 1 || isLoadingMore || loading}
        className={`h-8 flex items-center px-4 rounded-full text-sm font-medium transition-colors bg-deep-mocha-800/80 border border-deep-mocha-600/50 shadow-sm ${
          displayPage <= 1 || isLoadingMore
            ? "text-deep-mocha-500 cursor-not-allowed"
            : "text-deep-mocha-200 hover:bg-deep-mocha-700"
        }`}
      >
        Prev
      </button>

      <div className="inline-flex items-center rounded-full bg-deep-mocha-800/80 p-1 border border-deep-mocha-600/50 shadow-sm">
        {(() => {
          const elems: React.ReactNode[] = [];
          const displayTotal = speciesTotalPages;
          const windowSize = 10;
          const half = Math.floor(windowSize / 2);

          let start = Math.max(1, Math.min(highlightPage - half, Math.max(1, displayTotal - windowSize + 1)));
          let end = start + windowSize - 1;
          if (end > displayTotal) end = displayTotal;

          const renderHighlight = Math.min(Math.max(highlightPage, start), end);

          for (let p = start; p <= end; p++) {
            const isHighlighted = p === renderHighlight;
            elems.push(
              <button
                key={`p-${p}`}
                onClick={() => gotoPage(p)}
                className={`h-8 flex items-center px-3 py-1 mx-0.5 rounded-full text-sm font-medium transition-colors ${
                  isHighlighted ? "bg-hunter-green-500 text-white" : "text-deep-mocha-200 hover:bg-deep-mocha-700"
                }`}
                aria-current={isHighlighted ? "page" : undefined}
              >
                {p}
              </button>
            );
          }

          return elems;
        })()}
      </div>

      <button
        onClick={() => gotoPage(displayPage + 1)}
        disabled={displayPage >= speciesTotalPages || isLoadingMore || loading}
        className={`h-9 flex items-center px-5 rounded-full text-sm font-medium transition-colors bg-deep-mocha-800/80 border border-deep-mocha-600/50 shadow-sm ${
          displayPage >= speciesTotalPages || isLoadingMore
            ? "text-deep-mocha-500 cursor-not-allowed"
            : "text-deep-mocha-200 hover:bg-deep-mocha-700"
        }`}
      >
        Next
      </button>
    </div>
  );
}
