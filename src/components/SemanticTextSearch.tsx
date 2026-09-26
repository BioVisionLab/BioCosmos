"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { FlaskConical } from "lucide-react";
import { SemanticSearchDescription } from "./SemanticSearchFunctions";
import SearchForm from "./SearchForm";
import { SEARCH_PANEL } from "./searchPanel";

export default function SemanticSearchBar() {
  const router = useRouter();
  const [searchError, setSearchError] = useState<string | null>(null);

  const handleSearch = async (query: string, mode: string) => {
    setSearchError(null);

    try {
      if (!query || query.length < 3) {
        throw new Error("Search query must be at least 3 characters long");
      }

      router.push(`/search?q=${encodeURIComponent(query)}&mode=${mode}`);
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
        <SemanticSearchDescription />
      </div>
      <div className="w-full">
        <SearchForm
          mode="semantic"
          icon={FlaskConical}
          onSubmit={handleSearch}
          placeholder="Orange butterfly with black lines"
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
