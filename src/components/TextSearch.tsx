// Conventional Text Search to query the database based on user input
"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import SearchFieldSelect, { type SearchFieldGroup } from "./SearchFieldSelect";
import SearchForm from "./SearchForm";
import { SEARCH_PANEL } from "./searchPanel";
import { TRAIT_FIELD_OPTIONS } from "@/lib/dbSearch";

const FIELD_GROUPS: SearchFieldGroup[] = [
  { options: [{ value: "all", label: "All Fields" }] },
  {
    label: "Taxonomy",
    options: [
      { value: "kingdom", label: "Kingdom" },
      { value: "phylum", label: "Phylum" },
      { value: "class", label: "Class" },
      { value: "order", label: "Order" },
      { value: "family", label: "Family" },
      { value: "species", label: "Species" },
    ],
  },
  {
    label: "Specimen Metadata",
    options: [
      { value: "common_name", label: "Common Name" },
      { value: "class_dv", label: "Dorso/Ventral View" },
      { value: "sex", label: "Sex" },
      { value: "life_stage", label: "Life Stage" },
      { value: "source_db", label: "Source Database" },
    ],
  },
  {
    label: "Geography",
    options: [
      { value: "country", label: "Country" },
      { value: "state_province", label: "State / Province" },
      { value: "coordinate", label: "Coordinate (10,000 km² area)" },
    ],
  },
  { label: "Traits (LepTraits)", options: TRAIT_FIELD_OPTIONS },
];

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
    <div
      className={`${SEARCH_PANEL} flex flex-col items-center justify-center`}
    >
      <div className="mb-4 text-center text-deep-mocha-700 dark:text-deep-mocha-300 text-sm">
        <p>
          Conventional text-based search. Filter results by species, family, or
          other keywords. Results are ranked by relevance to your query.
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
        <SearchFieldSelect
          id="home-search-field-select"
          value={field}
          onChange={setField}
          groups={FIELD_GROUPS}
          className="w-full min-w-0 max-w-[220px]"
        />
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
  );
}
