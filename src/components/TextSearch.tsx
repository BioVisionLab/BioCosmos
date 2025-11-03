"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Search, FlaskConical } from "lucide-react"; // Import icons and Loader2

const LOCAL_STORAGE_KEY = "searchMode"; // Key for localStorage
export default function SemanticSearchBar() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState("");
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isSearching] = useState(false); // No actual search; keep false

  const handleSearchSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = searchTerm.trim();
    if (!query) return;

    setSearchError(null);

    // Navigate to the search page with query and mode
    const mode = "semantic";
    // TODO: handle 2 modes, semantic and text search
    router.push(`/search?q=${encodeURIComponent(query)}&mode=${mode}`);
  };

  return (
    <div className="w-full max-w-2xl mx-auto mb-6 bg-emerald-50/50 dark:bg-gray-800/50 p-6 rounded-3xl">
      <div className="mb-4 text-center text-gray-600 dark:text-gray-400 text-sm">
        <p>
          AI-powered search using natural language descriptions. Try describing
          a species' appearance, such as "orange butterfly with black lines".
        </p>
      </div>
      <form
        onSubmit={handleSearchSubmit}
        className="flex flex-col gap-2"
        aria-label="Species search form"
      >
        {/* Input + Actions */}
        <div className="flex items-center gap-2 w-full h-12">
          <div
            className={`
        relative flex items-stretch gap-2 rounded-l-2xl px-4 py-2
        bg-white/70 dark:bg-gray-800/60 backdrop-blur
        ring-1 ring-gray-200 dark:ring-gray-700
        shadow-sm hover:shadow-md transition-all
        focus-within:ring-2 focus-within:ring-green-500/60
        w-full h-full
        `}
          >
            {/* Left Icon */}
            <div className="flex items-center">
              <FlaskConical className="h-5 w-5 text-green-600 dark:text-green-300 transition-colors" />
            </div>

            {/* Text Input */}
            <input
              type="text"
              aria-label={"Semantic species search input"}
              placeholder={
                "Describe species traits, e.g., 'butterfly with orange wings and black lines'"
              }
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className={`
          flex-1 bg-transparent border-0 focus:outline-none
          placeholder:text-gray-400 dark:placeholder:text-gray-500
          text-gray-800 dark:text-gray-100
          text-sm md:text-base
          disabled:opacity-60
        `}
            />
          </div>
          {/* Submit button */}
          {/* Loading spinner */}
          <div className="col-span-2 flex items-center h-full">
            {/* {isSearching && (
              <div className="flex items-center pr-1">
                <Loader2 className="w-6 animate-spin text-green-500" />
              </div>
            )} */}
            <button
              type="submit"
              disabled={isSearching || !searchTerm.trim()}
              className={`
              flex items-center justify-center 
              px-5 text-sm font-medium rounded-r-2xl
              bg-green-600 text-white hover:bg-green-700
              ring-1 ring-emerald-200 dark:ring-emerald-600
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors h-full backdrop-blur
              `}
              aria-label="Submit species search"
            >
              {isSearching ? "Searching..." : "Search"}
            </button>
          </div>
        </div>
        {/* Mode Toggle
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            <span className="inline-block h-2 w-2 rounded-full bg-green-500 animate-pulse" />
            {isSemantic
              ? "Semantic mode: natural language & visual description"
              : "Text mode: exact / partial species names"}
          </div>
        </div> */}
      </form>

      {searchError && (
        <p
          role="alert"
          className="text-xs text-red-500 mt-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-md px-3 py-2"
        >
          {searchError}
        </p>
      )}
    </div>
  );
}
