"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ImageSearchResult } from "./components/ImageSearchResult";
import SemanticSearchResults from "./components/SemanticSearchResults";
import { DbSearch } from "./components/DbSearchResults";

const MODE_OPTIONS = ["semantic", "text", "image"] as const;
type SearchMode = (typeof MODE_OPTIONS)[number];

function isValidMode(mode: string | null): mode is SearchMode {
  return mode !== null && MODE_OPTIONS.includes(mode as SearchMode);
}

function SearchContent() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";
  const mode = searchParams.get("mode");
  const field = searchParams.get("field") || "all";

  if (!mode) {
    return (
      <div className="p-4 text-center">
        <p className="text-gray-600">Please specify a search mode.</p>
        <p className="text-sm text-gray-500 mt-2">
          Valid modes: {MODE_OPTIONS.join(", ")}
        </p>
      </div>
    );
  }

  if (!isValidMode(mode)) {
    return (
      <div className="p-4 text-center">
        <p className="text-red-600">Invalid search mode: {mode}</p>
        <p className="text-sm text-gray-500 mt-2">
          Valid modes: {MODE_OPTIONS.join(", ")}
        </p>
      </div>
    );
  }

  if (!query && mode !== "image") {
    return (
      <div className="p-4 text-center text-gray-600">
        Please enter a search query.
      </div>
    );
  }

  switch (mode) {
    case "semantic":
      return <SemanticSearchResults query={query} />;
    case "text":
      return <DbSearch query={query} initialField={field} />;
    case "image":
      return <ImageSearchResult imageUrl={query} />;
  }
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-4">Loading search results...</div>}>
      <div>
        <SearchContent />
        {/* spacer between search results and the site footer */}
        <div className="h-9 md:h-16 lg:h-18" aria-hidden="true" />
      </div>
    </Suspense>
  );
}
