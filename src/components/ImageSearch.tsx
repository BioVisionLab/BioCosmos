"use client";

import React, { useState, useCallback } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { UploadCloud, Image as ImageIcon, Search } from "lucide-react";
import { setSearchImage } from "@/lib/imageSearchStore";

export default function ImageSearch({ fileUrl }: { fileUrl?: string }) {
  const [selectedFileUrl, setSelectedFileUrl] = useState<string | null>(
    fileUrl || null
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
      event.currentTarget.classList.add("border-emerald-500"); // Highlight effect
    },
    []
  );

  const handleDragLeave = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      event.currentTarget.classList.remove("border-emerald-500");
    },
    []
  );

  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.currentTarget.classList.remove("border-emerald-500");
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
    <div className="w-full max-w-2xl mx-auto mb-6">
      <div className="flex flex-col gap-3">
        <div
          className="relative flex flex-col items-center justify-center p-4 rounded-2xl bg-white/70 dark:bg-gray-800/60 backdrop-blur shadow-sm hover:shadow-md transition-all"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <div className="flex flex-col items-center border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md p-4 text-center mb-2 w-full">
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
                  : "text-emerald-700 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/30"
              }`}
            >
              {selectedFileUrl ? "Change Image" : "Upload Image"}
            </label>
            {!selectedFileUrl && (
              <div
                id="upload-instructions"
                className="text-center text-xs text-gray-500"
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
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-br from-emerald-500 to-teal-600 text-white rounded-md hover:shadow-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 disabled:from-gray-300 disabled:to-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed dark:disabled:from-gray-600 dark:disabled:to-gray-600 dark:disabled:text-gray-400 transition-all"
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
            className="text-xs text-red-500 mt-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-md px-3 py-2"
          >
            {searchError}
          </p>
        )}
      </div>
    </div>
  );
}
