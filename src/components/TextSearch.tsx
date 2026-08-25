// Conventional Text Search to query the database based on user input
"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import SearchForm from "./SearchForm";

export default function TextSearch() {
  const router = useRouter();
  const [searchError, setSearchError] = useState<string | null>(null);
  const [field, setField] = useState("all");

  const handleSearch = async (query: string, mode: string) => {
    setSearchError(null);

    try {
      if (!query || query.length < 3) {
        throw new Error("Search query must be at least 3 characters long");
      }

      router.push(
        `/search?q=${encodeURIComponent(query)}&mode=${mode}&field=${encodeURIComponent(field)}`,
      );
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : "An error occurred during search";
      setSearchError(errorMessage);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-[2px] mb-6 rounded-3xl bg-hunter-green-300 dark:bg-hunter-green-700">
      <div className="bg-hunter-green-200 dark:bg-hunter-green-900 p-6 rounded-[calc(1.5rem-2px)] flex flex-col items-center">
        <div className="mb-4 text-center text-deep-mocha-700 dark:text-deep-mocha-300 text-sm">
          <p>
            Conventional text-based search. Filter results by species, family,
            or other keywords. Results are ranked by relevance to your query.
          </p>
        </div>
        <div className="w-full">
          <SearchForm
            mode="text"
            icon={Search}
            onSubmit={handleSearch}
            placeholder="Danaus plexippus"
          />
        </div>

        <div className="mt-4 flex items-center justify-center gap-3 text-sm text-deep-mocha-600 dark:text-deep-mocha-300 w-full">
          <label
            htmlFor="home-search-field-select"
            className="font-semibold tracking-wide uppercase text-xs text-deep-mocha-500 dark:text-deep-mocha-400 whitespace-nowrap"
          >
            Search by:
          </label>
          <div className="relative w-full max-w-[200px]">
            <select
              id="home-search-field-select"
              value={field}
              onChange={(e) => setField(e.target.value)}
              className="appearance-none w-full bg-white/70 dark:bg-deep-mocha-800/60 backdrop-blur border border-deep-mocha-200 dark:border-deep-mocha-700 rounded-xl px-4 py-2 pr-10 focus:outline-none focus:ring-2 focus:ring-hunter-green-500/60 shadow-xs hover:border-hunter-green-500/50 hover:shadow-sm transition-all text-deep-mocha-800 dark:text-deep-mocha-100 cursor-pointer font-medium"
            >
              <option value="all">All Fields</option>
              <optgroup
                label="Taxonomy"
                className="bg-deep-mocha-100 dark:bg-deep-mocha-900 text-deep-mocha-500 dark:text-deep-mocha-400 font-semibold text-xs"
              >
                <option
                  value="kingdom"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Kingdom
                </option>
                <option
                  value="phylum"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Phylum
                </option>
                <option
                  value="class"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Class
                </option>
                <option
                  value="order"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Order
                </option>
                <option
                  value="family"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Family
                </option>
                <option
                  value="species"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Species
                </option>
              </optgroup>
              <optgroup
                label="Specimen Metadata"
                className="bg-deep-mocha-100 dark:bg-deep-mocha-900 text-deep-mocha-500 dark:text-deep-mocha-400 font-semibold text-xs"
              >
                <option
                  value="common_name"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Common Name
                </option>
                <option
                  value="class_dv"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Dorso/Ventral View
                </option>
                <option
                  value="sex"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Sex
                </option>
                <option
                  value="life_stage"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Life Stage
                </option>
                <option
                  value="source_db"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Source Database
                </option>
              </optgroup>
              <optgroup
                label="Geography"
                className="bg-deep-mocha-100 dark:bg-deep-mocha-900 text-deep-mocha-500 dark:text-deep-mocha-400 font-semibold text-xs"
              >
                <option
                  value="coordinate"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Coordinate (10,000 km² area)
                </option>
              </optgroup>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-deep-mocha-500 dark:text-deep-mocha-400">
              <svg
                className="fill-current h-4 w-4"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
              >
                <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
              </svg>
            </div>
          </div>
        </div>

        {searchError && (
          <p
            role="alert"
            className="text-xs text-burnt-peach-500 mt-2 bg-burnt-peach-50 dark:bg-burnt-peach-900/30 border border-burnt-peach-200 dark:border-burnt-peach-800 rounded-md px-3 py-2 w-full"
          >
            {searchError}
          </p>
        )}
      </div>
    </div>
  );
}
