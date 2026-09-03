"use client";

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
            <svg
              className="h-5 w-5"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
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
            <svg
              className="h-5 w-5"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </nav>
      </div>
    </div>
  );
}
