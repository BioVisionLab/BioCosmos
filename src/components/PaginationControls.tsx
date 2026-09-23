"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import React from "react";

const BTN =
  "relative inline-flex items-center px-4 py-2 border border-deep-mocha-200 dark:border-deep-mocha-700 text-sm font-medium rounded-xl text-deep-mocha-700 dark:text-deep-mocha-200 bg-white/70 dark:bg-deep-mocha-800/60 hover:bg-hunter-green-500/10 dark:hover:bg-hunter-green-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer";
const ARROW_BTN =
  "relative inline-flex items-center px-3 py-2 border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/70 dark:bg-deep-mocha-800/60 text-sm font-medium text-deep-mocha-500 dark:text-deep-mocha-400 hover:bg-hunter-green-500/10 dark:hover:bg-hunter-green-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer";
const HIGHLIGHT =
  "font-semibold text-hunter-green-600 dark:text-hunter-green-400";

export default function PaginationControls({
  currentPage,
  totalPages,
  totalItems,
  itemsPerPage,
  label,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  itemsPerPage: number;
  label: string;
  onPageChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;
  const start = (currentPage - 1) * itemsPerPage + 1;
  const end = Math.min(currentPage * itemsPerPage, totalItems);

  return (
    <div className="mt-4 flex items-center justify-between px-4 py-3 bg-white/30 dark:bg-deep-mocha-800/30 backdrop-blur border border-deep-mocha-200 dark:border-deep-mocha-700/80 rounded-2xl">
      <div className="flex-1 flex justify-between sm:hidden">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className={BTN}
        >
          Previous
        </button>
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className={`ml-3 ${BTN}`}
        >
          Next
        </button>
      </div>
      <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
        <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
          Showing <span className={HIGHLIGHT}>{start}</span> to{" "}
          <span className={HIGHLIGHT}>{end}</span> of{" "}
          <span className={HIGHLIGHT}>{totalItems}</span> {label}
        </p>
        <nav
          className="relative z-0 inline-flex rounded-md shadow-xs -space-x-px"
          aria-label={`${label} pagination`}
        >
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            className={`rounded-l-xl ${ARROW_BTN}`}
          >
            <span className="sr-only">Previous</span>
            <ChevronLeft className="h-5 w-5" aria-hidden="true" />
          </button>
          <span className="relative inline-flex items-center px-4 py-2 border-t border-b border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/50 dark:bg-deep-mocha-800/40 text-sm font-medium text-deep-mocha-700 dark:text-deep-mocha-300">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            className={`rounded-r-xl ${ARROW_BTN}`}
          >
            <span className="sr-only">Next</span>
            <ChevronRight className="h-5 w-5" aria-hidden="true" />
          </button>
        </nav>
      </div>
    </div>
  );
}
