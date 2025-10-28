import { MlResultItems, searchFromImage } from "@/lib/ml_search";
import { Suspense, useEffect, useState } from "react";
import SpeciesSearchResultCard from "./ResultCard";
import { ImageLoading } from "@/components/Loadings";

export function ImageSearchResult({ imageUrl }: { imageUrl: string }) {
  const [results, setResults] = useState<MlResultItems[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!imageUrl) return;

    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = new FormData();
        // We convert imageBlob to File object
        const response = await fetch(imageUrl);
        const imageBlob = await response.blob();
        const file = new File([imageBlob], "search-image", {
          type: imageBlob.type,
        });
        data.append("image", file);
        const results = await searchFromImage(data);
        setResults(results);
      } catch (err) {
        console.error("Error during image search:", err);
        setError(
          err instanceof Error
            ? err.message
            : "An unknown error occurred during image search."
        );
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [imageUrl]);

  return (
    <div className="items-center max-w-7xl w-full px-4 mx-auto">
      <div className="mb-4">
        <a href="/" className="text-blue-600 hover:underline">
          &larr; Back to Home
        </a>
      </div>
      <div className="mt-2 mb-6 text-center">
        <h1 className="text-xl sm:text-4xl font-extrabold tracking-tight font-serif bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-transparent bg-clip-text drop-shadow">
          Search Results
        </h1>
      </div>
      <div className="mt-5">
        {loading ? (
          <div className="flex flex-col items-center mt-24">
            <ImageLoading size={240} msg="Searching for species" />
          </div>
        ) : error ? (
          <p className="text-red-500">Error: {error}</p>
        ) : results.length === 0 ? (
          <p>No results found for "{imageUrl}".</p>
        ) : (
          <div>
            <p className="mb-4">
              Found {results.length} results for "{imageUrl}":
            </p>
            <div className="grid grid-flow-row grid-cols-[repeat(auto-fill,160px)] gap-4">
              {results.map((item) => (
                <Suspense
                  key={item.imgId}
                  fallback={<div>Loading species...</div>}
                >
                  <SpeciesSearchResultCard species={item} />
                </Suspense>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
