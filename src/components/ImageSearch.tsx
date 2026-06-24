"use client";

import React, { useState, useCallback } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { UploadCloud, Image as ImageIcon, Search } from "lucide-react";
import { setSearchImage } from "@/lib/imageSearchStore";

export default function ImageSearch({ fileUrl }: { fileUrl?: string }) {
  const [selectedFileUrl, setSelectedFileUrl] = useState<string | null>(
    fileUrl || null,
  );
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const router = useRouter();

  // Handle file selection from input
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // Exclude avif format because it's not supported by the backend
    if (file && file.type.startsWith("image/") && file.type !== "image/avif") {
      const fileUrl = URL.createObjectURL(file);
      setSearchImage(file, fileUrl);
      setSelectedFileUrl(fileUrl);
      setSearchError(null); // Clear previous error on new selection
    } else {
      setSelectedFileUrl(null);
      setSearchError(
        "Please select a valid image file. Supported formats: JPEG, JPG, PNG, WEBP."
      );
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
        `/search?q=${encodeURIComponent(selectedFileUrl)}&mode=image`,
      );
    } catch (err) {
      console.error("Image search error:", err);
      setSearchError(
        err instanceof Error
          ? err.message
          : "An unknown image search error occurred.",
      );
    } finally {
      setIsSearching(false);
    }
  };

  // Handle drag and drop (basic implementation)
  const handleDragOver = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault(); // Necessary to allow drop
      event.currentTarget.classList.add("border-hunter-green-500"); // Highlight effect
    },
    [],
  );

  const handleDragLeave = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      event.currentTarget.classList.remove("border-hunter-green-500");
    },
    [],
  );

  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.currentTarget.classList.remove("border-hunter-green-500");
    const file = event.dataTransfer.files?.[0];
    if (file && file.type.startsWith("image/") && file.type !== "image/avif") {
      const fileUrl = URL.createObjectURL(file);
      setSearchImage(file, fileUrl);
      setSelectedFileUrl(fileUrl);
      setSearchError(null);
    } else {
      setSelectedFileUrl(null);
      setSearchError("Please drop a valid image file.");
    }
  }, []);

  return (
    <div className="w-full max-w-2xl mx-auto p-[2px] mb-6 rounded-3xl bg-gradient-to-br from-hunter-green-400 via-pacific-blue-400 to-frozen-water-500 dark:from-hunter-green-600 dark:via-pacific-blue-600 dark:to-frozen-water-700 animate-spin-slow">
      <div className="bg-hunter-green-50/50 dark:bg-deep-mocha-800/50 p-6 rounded-3xl backdrop-blur-sm flex flex-col gap-3">
        <div
          className="relative flex flex-col items-center justify-center p-4 rounded-2xl bg-white/70 dark:bg-deep-mocha-800/60 backdrop-blur shadow-sm hover:shadow-md transition-all"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <div className="flex flex-col items-center border-2 border-dashed border-deep-mocha-600 dark:border-deep-mocha-200 rounded-md p-4 text-center mb-2 w-full">
            {selectedFileUrl ? (
              <div className="relative w-full max-h-80 mb-2 flex items-center justify-center overflow-hidden rounded">
                <Image
                  src={selectedFileUrl}
                  alt="Selected preview"
                  width={800}
                  height={320}
                  className="w-full h-auto max-h-80 object-contain"
                  unoptimized
                />
              </div>
            ) : (
              <UploadCloud className="h-10 w-10 text-deep-mocha-500 dark:text-deep-mocha-400 mb-2" />
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
                  ? "text-deep-mocha-400 cursor-not-allowed"
                  : "text-hunter-green-700 dark:text-hunter-green-400 hover:bg-hunter-green-50 dark:hover:bg-hunter-green-900/30"
              }`}
            >
              {selectedFileUrl ? "Change Image" : "Upload Image"}
            </label>
            {!selectedFileUrl && (
              <div
                id="upload-instructions"
                className="text-center text-xs text-deep-mocha-600 dark:text-deep-mocha-300"
              >
                <p>or drag & drop</p>
                <p className="mt-4">
                  Supported formats: JPEG, JPG, PNG, and WEBP.
                </p>
              </div>
            )}
          </div>
          <button
            onClick={handleImageSearch}
            disabled={!selectedFileUrl || isSearching}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-br from-hunter-green-600 to-pacific-blue-700 text-white rounded-md hover:shadow-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-hunter-green-500 disabled:from-deep-mocha-300 disabled:to-deep-mocha-300 disabled:text-deep-mocha-500 disabled:cursor-not-allowed dark:disabled:from-deep-mocha-600 dark:disabled:to-deep-mocha-600 dark:disabled:text-deep-mocha-400 transition-all"
          >
            {isSearching ? (
              <>
                <ImageIcon className="h-5 w-5 animate-pulse" /> Searching...
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
            className="text-xs text-burnt-peach-500 mt-2 bg-burnt-peach-50 dark:bg-burnt-peach-900/30 border border-burnt-peach-200 dark:border-burnt-peach-800 rounded-md px-3 py-2"
          >
            {searchError}
          </p>
        )}
      </div>
    </div>
  );
}
