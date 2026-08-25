"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { FlaskConical } from "lucide-react";
import SearchForm from "./SearchForm";

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
    <div className="w-full max-w-2xl mx-auto p-[2px] mb-6 rounded-3xl bg-gradient-to-br from-hunter-green-400 via-pacific-blue-400 to-frozen-water-500 dark:from-hunter-green-600 dark:via-pacific-blue-600 dark:to-frozen-water-700 animate-spin-slow">
      <div className="bg-hunter-green-50/50 dark:bg-deep-mocha-800/50 p-6 rounded-3xl backdrop-blur-sm">
        <div className="mb-4 text-center text-deep-mocha-700 dark:text-deep-mocha-300 text-sm">
          <p>
            AI-powered search using natural language descriptions. Try
            describing a species' appearance, such as "orange butterfly with
            black lines".
          </p>
        </div>
        <SearchForm
          mode="semantic"
          icon={FlaskConical}
          onSubmit={handleSearch}
          placeholder="Orange butterfly with black lines"
        />
        {searchError && (
          <p
            role="alert"
            className="text-xs text-burnt-peach-500 mt-2 bg-burnt-peach-50 dark:bg-burnt-peach-900/30 border border-burnt-peach-200 dark:border-burnt-peach-800 rounded-md px-3 py-2"
          >
            {searchError}
          </p>
        )}
      </div>
    </div>
  );
}
