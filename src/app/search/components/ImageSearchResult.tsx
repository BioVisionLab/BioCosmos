import { MlResultItems, searchFromImage } from "@/lib/ml_search";
import { Suspense, useEffect, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import { MLSearchResultCard, TopResultCard } from "./MlResultCard";
import Tips from "@/components/Tips";
import { getSearchImage, clearSearchImage } from "@/lib/imageSearchStore";

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

        // Prefer the original File from the in-memory store (preserves MIME type and name)
        const storedFile = getSearchImage(imageUrl);
        if (storedFile) {
          data.append("image", storedFile);
          clearSearchImage();
        } else {
          // Fallback for page refresh / direct URL access: re-fetch blob and sniff MIME
          const response = await fetch(imageUrl);
          const imageBlob = await response.blob();

          let mimeType = imageBlob.type;
          if (!mimeType) {
            const arr = new Uint8Array(await imageBlob.slice(0, 12).arrayBuffer());
            const isJpeg = arr[0] === 0xff && arr[1] === 0xd8;
            const isPng =
              arr[0] === 0x89 &&
              arr[1] === 0x50 &&
              arr[2] === 0x4e &&
              arr[3] === 0x47;
            const isWebp =
              arr[0] === 0x52 &&
              arr[1] === 0x49 &&
              arr[2] === 0x46 &&
              arr[3] === 0x46 &&
              arr[8] === 0x57 &&
              arr[9] === 0x45 &&
              arr[10] === 0x42 &&
              arr[11] === 0x50;
            if (isJpeg) mimeType = "image/jpeg";
            else if (isPng) mimeType = "image/png";
            else if (isWebp) mimeType = "image/webp";
            else mimeType = "application/octet-stream";
          }

          const file = new File([imageBlob], "search-image", { type: mimeType });
          data.append("image", file);
        }

        const results = await searchFromImage(data);
        setResults(results);
      } catch (err) {
        console.error("Error during image search:", err);
        setError(
          err instanceof Error
            ? err.message
            : "An unknown error occurred during image search.",
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
      <div className="mt-8 mb-6 text-center">
        <h1 className="text-xl sm:text-4xl font-extrabold tracking-tight font-serif bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-transparent bg-clip-text drop-shadow">
          Image Similarity Search
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
          <MlImageResultCard data={results} />
        )}
      </div>
    </div>
  );
}

function MlImageResultCard({ data }: { data: MlResultItems[] }) {
  return (
    <div className="mt-8">
      <div id="top-results" className="mb-6">
        <Suspense fallback={<div>Loading top species...</div>}>
          <TopResultCard data={data[0]} />
        </Suspense>
      </div>
      <div className="mb-4">
        <h2
          id="other-results"
          className="text-lg text-gray-700 dark:text-gray-200"
        >
          Found {data.length} other results"
        </h2>
        <Tips message="Click on an image to view species page" />
      </div>
      <p className="mb-4">Found {data.length} results</p>
      <div className="grid grid-flow-row grid-cols-[repeat(auto-fill,160px)] gap-4">
        {data.slice(1).map((item) => (
          <Suspense key={item.imgId} fallback={<div>Loading species...</div>}>
            <MLSearchResultCard data={item} />
          </Suspense>
        ))}
      </div>
    </div>
  );
}
