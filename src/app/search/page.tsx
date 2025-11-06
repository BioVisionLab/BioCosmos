"use client";

import { useSearchParams } from "next/navigation";
import TextSearchResults from "./components/TextSearchResults";

export default function SearchPage() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";
  const mode = searchParams.get("mode") || "semantic"; // default to semantic mode
  return <TextSearchResults query={query} mode={mode} />;
}
