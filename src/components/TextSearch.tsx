// Conventional Text Search to query the database based on user input
"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import SearchForm from "./SearchForm";

export default function TextSearch() {
  const router = useRouter();
  const [searchError, setSearchError] = useState<string | null>(null);

  const handleSearch = async (query: string, mode: string) => {
    setSearchError(null);

    try {
      // If you need to validate or pre-process before navigation
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
    <div className="w-full max-w-2xl mx-auto mb-6 bg-emerald-50/50 dark:bg-gray-800/50 p-6 rounded-3xl">
      <div className="mb-4 text-center text-gray-600 dark:text-gray-400 text-sm">
        <p>
          Conventional text-based search to query BIOCOSMOS database. Try
          searching for "danaus plexippus" or "monarch".
        </p>
      </div>
      <SearchForm
        mode="text"
        icon={Search}
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
  );
}
