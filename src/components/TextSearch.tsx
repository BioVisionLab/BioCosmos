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

      router.push(`/search?q=${encodeURIComponent(query)}&mode=${mode}&field=${encodeURIComponent(field)}`);
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : "An error occurred during search";
      setSearchError(errorMessage);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto mb-6 bg-emerald-200/50 dark:bg-gray-700/50 p-6 rounded-3xl flex flex-col items-center">
      <div className="mb-4 text-center text-gray-600 dark:text-gray-400 text-sm">
        <p>
          Conventional text-based search to query BIOCOSMOS database. Search by
          species, family, or other keywords. Results are ranked by relevance to
          your query.
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
      
      <div className="mt-4 flex items-center justify-center gap-3 text-sm text-gray-600 dark:text-gray-300">
        <label htmlFor="home-search-field-select" className="font-semibold tracking-wide uppercase text-xs text-gray-500 dark:text-gray-400">
          Search by:
        </label>
        <div className="relative">
          <select
            id="home-search-field-select"
            value={field}
            onChange={(e) => setField(e.target.value)}
            className="appearance-none bg-white/70 dark:bg-gray-800/60 backdrop-blur border border-gray-200 dark:border-gray-700 rounded-xl px-4 py-2 pr-10 focus:outline-none focus:ring-2 focus:ring-emerald-500/60 shadow-xs hover:border-emerald-500/50 hover:shadow-sm transition-all text-gray-800 dark:text-gray-100 cursor-pointer font-medium"
          >
            <option value="all">All Fields</option>
            <option value="species">Species</option>
            <option value="common_name">Common Name</option>
            <option value="family">Family</option>
            <option value="class_dv">Class DV (View)</option>
            <option value="tax_rank">Taxonomic Rank</option>
            <option value="tax_status">Taxonomic Status</option>
            <option value="sex">Sex</option>
            <option value="life_stage">Life Stage</option>
            <option value="lat">Latitude</option>
            <option value="lon">Longitude</option>
            <option value="source_db">Source Database</option>
            <option value="kingdom">Kingdom</option>
            <option value="phylum">Phylum</option>
            <option value="class">Class</option>
            <option value="order">Order</option>
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-gray-500 dark:text-gray-400">
            <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
              <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"/>
            </svg>
          </div>
        </div>
      </div>

      {searchError && (
        <p
          role="alert"
          className="text-xs text-red-500 mt-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-md px-3 py-2 w-full"
        >
          {searchError}
        </p>
      )}
    </div>
  );
}
