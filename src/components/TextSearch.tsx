"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Search, FlaskConical, Loader2 } from "lucide-react"; // Import icons and Loader2

// Define the type for the semantic result object from the Python service
interface SemanticResultItem {
  species_folder: string;
  best_image_filename: string;
}

const LOCAL_STORAGE_KEY = "searchMode"; // Key for localStorage
export default function SearchBar() {
  const router = useRouter();

  // Initialize state to default (false) to match server render
  const [isSemantic, setIsSemantic] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [isMounted, setIsMounted] = useState(false); // Track if component is mounted
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isSearching] = useState(false); // No actual search; keep false

  // Effect runs only on the client after mount
  useEffect(() => {
    // Read from localStorage and update state
    const storedMode = localStorage.getItem(LOCAL_STORAGE_KEY);
    setIsSemantic(storedMode === "semantic");
    // Mark as mounted
    setIsMounted(true);
  }, []); // Empty dependency array ensures it runs only once on mount

  // Effect to update localStorage when state changes (dependent on isMounted)
  useEffect(() => {
    // Only write to localStorage after initial mount & state hydration
    if (isMounted) {
      localStorage.setItem(LOCAL_STORAGE_KEY, isSemantic ? "semantic" : "text");
    }
  }, [isSemantic, isMounted]);

  const toggleSearchMode = () => {
    setIsSemantic((prev) => !prev);
    setSearchTerm(""); // Clear search term on mode switch
    setSearchError(null); // Clear errors
  };

  const handleSearchSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = searchTerm.trim();
    if (!query) return;

    setSearchError(null);

    // Navigate to the search page with query and mode
    const mode = isSemantic ? "semantic" : "text";
    router.push(`/search?q=${encodeURIComponent(query)}&mode=${mode}`);
  };

  return (
    <div className="w-full max-w-2xl mx-auto mb-6">
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
        w-full
        `}
          >
            {/* Left Icon */}
            <div className="flex items-center">
              {isSemantic ? (
                <FlaskConical className="h-5 w-5 text-green-600 dark:text-green-300 transition-colors" />
              ) : (
                <Search className="h-5 w-5 text-gray-400 dark:text-gray-500 transition-colors" />
              )}
            </div>

            {/* Text Input */}
            <input
              type="text"
              aria-label={
                isSemantic
                  ? "Semantic species search input"
                  : "Text species search input"
              }
              placeholder={
                isMounted && isSemantic
                  ? "Describe a species: e.g. orange butterfly with black lines"
                  : "Search species by name..."
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
            <button
              type="button"
              onClick={toggleSearchMode}
              disabled={!isMounted}
              className={`
          relative inline-flex items-center rounded-full p-1 transition-colors
          focus:outline-none focus:ring-2 focus:ring-green-500/70
          
          ${
            isSemantic
              ? "bg-green-600/20"
              : "bg-gray-300/40 dark:bg-gray-700/60"
          }
          disabled:opacity-50 disabled:cursor-not-allowed
        `}
              aria-pressed="false"
              aria-label="Toggle semantic search mode"
              title={
                !isMounted
                  ? "Loading mode..."
                  : isSemantic
                  ? "Switch to Text Search"
                  : "Switch to Semantic Search"
              }
            >
              <span
                className={`
          flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-full
          transition-all
          ${
            isSemantic
              ? "bg-green-500 text-white shadow"
              : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 shadow"
          }
          `}
              >
                {isSemantic ? (
                  <span>Semantic</span>
                ) : (
                  <span className="text-gray-400 dark:text-gray-500 ">
                    Text
                  </span>
                )}
              </span>
            </button>
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
        {/* Mode Toggle */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            <span className="inline-block h-2 w-2 rounded-full bg-green-500 animate-pulse" />
            {isSemantic
              ? "Semantic mode: natural language & visual description"
              : "Text mode: exact / partial species names"}
          </div>
        </div>
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
