"use client";

import React, { useState, useCallback } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { UploadCloud, Image as Loader2, Search } from "lucide-react";

// Define the type for the semantic result object (consistent with HeaderClient)
interface SemanticResultItem {
  species_folder: string;
  best_image_filename: string;
}
export default function ImageSearch() {
  const [selectedFileUrl, setSelectedFileUrl] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const router = useRouter();

  // Handle file selection from input
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && file.type.startsWith("image/")) {
      setSelectedFileUrl(URL.createObjectURL(file));
      setPreviewUrl(URL.createObjectURL(file));
      setSearchError(null); // Clear previous error on new selection
    } else {
      setSelectedFileUrl(null);
      setPreviewUrl(null);
      setSearchError("Please select a valid image file.");
    }
    // Reset the input value to allow selecting the same file again
    event.target.value = "";
  };

  // Handle search submission
  const handleImageSearch = async () => {
    if (!selectedFileUrl) {
      setSearchError("Please select an image first.");
      return;
    }

    setIsSearching(true);
    setSearchError(null);

    try {
      // Navigate to search page with results
      router.push(
        `/search?q=${encodeURIComponent(selectedFileUrl)}&mode=image`
      );
    } catch (err) {
      console.error("Image search error:", err);
      setSearchError(
        err instanceof Error
          ? err.message
          : "An unknown image search error occurred."
      );
    } finally {
      setIsSearching(false);
    }
  };

  // Handle drag and drop (basic implementation)
  const handleDragOver = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault(); // Necessary to allow drop
      event.currentTarget.classList.add("border-green-500"); // Highlight effect
    },
    []
  );

  const handleDragLeave = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      event.currentTarget.classList.remove("border-green-500");
    },
    []
  );

  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.currentTarget.classList.remove("border-green-500");
    const file = event.dataTransfer.files?.[0];
    if (file && file.type.startsWith("image/")) {
      const fileUrl = URL.createObjectURL(file);
      setSelectedFileUrl(fileUrl);
      setPreviewUrl(fileUrl);
      setSearchError(null);
    } else {
      setSelectedFileUrl(null);
      setPreviewUrl(null);
      setSearchError("Please drop a valid image file.");
    }
  }, []);

  return (
    <div className="w-full max-w-2xl mx-auto mb-6">
      <div className="flex flex-col gap-3">
        <div
          className="relative flex flex-col items-center justify-center w-full p-4 rounded-2xl bg-white/70 dark:bg-gray-800/60 backdrop-blur ring-1 ring-gray-200 dark:ring-gray-700 shadow-sm hover:shadow-md transition-all"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <div className="flex flex-col items-center border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md p-4 text-center mb-3 w-full">
            {previewUrl ? (
              <div className="relative w-full aspect-square mb-2">
                <Image
                  src={previewUrl}
                  alt="Selected preview"
                  layout="fill"
                  objectFit="contain"
                  className="rounded"
                />
              </div>
            ) : (
              <UploadCloud className="h-10 w-10 text-gray-400 mb-2" />
            )}

            <input
              type="file"
              id="imageUpload"
              accept="image/*"
              onChange={handleFileChange}
              className="hidden"
              disabled={isSearching}
            />
            <label
              htmlFor="imageUpload"
              className={`text-sm font-medium cursor-pointer px-3 py-1 rounded ${
                isSearching
                  ? "text-gray-400 cursor-not-allowed"
                  : "text-green-700 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900"
              }`}
            >
              {selectedFileUrl ? "Change Image" : "Upload Image"}
            </label>
            {!selectedFileUrl && (
              <p className="text-xs text-gray-500 mt-1">or drag & drop</p>
            )}
          </div>

          <button
            onClick={handleImageSearch}
            disabled={!selectedFileUrl || isSearching}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-br from-green-500 to-green-600 text-white rounded-md hover:shadow-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:from-gray-300 disabled:to-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed dark:disabled:from-gray-600 dark:disabled:to-gray-600 dark:disabled:text-gray-400 transition-all"
          >
            {isSearching ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" /> Searching...
              </>
            ) : (
              <>
                <Search size={18} /> Search by Image
              </>
            )}
          </button>
        </div>

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
