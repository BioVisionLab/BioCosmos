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
    <div className="w-full max-w-2xl mx-auto p-[2px] mb-6 rounded-3xl bg-gradient-to-br from-emerald-400 via-teal-400 to-cyan-500 dark:from-emerald-600 dark:via-teal-600 dark:to-cyan-700 animate-spin-slow">
      <div className="bg-emerald-50/50 dark:bg-gray-800/50 p-6 rounded-3xl opacity-80 backdrop-blur-sm">
        <div className="mb-4 text-center text-gray-600 dark:text-gray-400 text-sm">
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
            className="text-xs text-red-500 mt-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-md px-3 py-2"
          >
            {searchError}
          </p>
        )}
      </div>
    </div>
  );
}
