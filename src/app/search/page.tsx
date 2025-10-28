"use client";

import { useSearchParams } from "next/navigation";
import TextSearchResults from "./components/TextSearchResults";
import { ImageSearchResult } from "./components/ImageSearchResult";

const mode_options = ["semantic", "text", "image"] as const;

export default function SearchPage() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";
  const mode = searchParams.get("mode") || null;

  if (mode && !mode_options.includes(mode as (typeof mode_options)[number])) {
    return <div className="p-4">Invalid search mode.</div>;
  }

  if (!mode) {
    return <div className="p-4">Please specify a search mode.</div>;
  }

  if (mode === "text" || mode === "semantic") {
    return <TextSearchResults query={query} />;
  }

  if (mode === "image") {
    return <ImageSearchResult imageUrl={query} />;
  }
}
