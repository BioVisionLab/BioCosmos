"use client";

import React, { useState, useCallback } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { UploadCloud, Image as ImageIcon, Loader2, Search } from "lucide-react";

// Define the type for the semantic result object (consistent with HeaderClient)
interface SemanticResultItem {
  species_folder: string;
  best_image_filename: string;
}

export default function ImageSearch() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const router = useRouter();

  // Handle file selection from input
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && file.type.startsWith("image/")) {
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setSearchError(null); // Clear previous error on new selection
    } else {
      setSelectedFile(null);
      setPreviewUrl(null);
      setSearchError("Please select a valid image file.");
    }
    // Reset the input value to allow selecting the same file again
    event.target.value = "";
  };

  // Convert file to base64
  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = (error) => reject(error);
    });
  };

  // Handle search submission
  const handleImageSearch = async () => {
    if (!selectedFile) {
      setSearchError("Please select an image first.");
      return;
    }

    setIsSearching(true);
    setSearchError(null);

    try {
      const base64Image = await fileToBase64(selectedFile);

      // Send base64 image to the backend API route
      const response = await fetch("/api/image-search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ image: base64Image }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.error ||
            `Image search failed with status ${response.status}`
        );
      }

      const results: SemanticResultItem[] = await response.json();

      if (results.length > 0) {
        // Navigate to search page with results
        router.push(
          `/search?ids=${encodeURIComponent(
            JSON.stringify(results)
          )}&mode=semantic`
        );
        // Optionally clear selection after successful search
        // setSelectedFile(null);
        // setPreviewUrl(null);
      } else {
        setSearchError("No similar species found for the uploaded image.");
        console.log("Image search returned empty results.");
      }
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
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setSearchError(null);
    } else {
      setSelectedFile(null);
      setPreviewUrl(null);
      setSearchError("Please drop a valid image file.");
    }
  }, []);

  // <<< Add console log here >>>
  console.log(
    `ImageSearchWidget render: isSearching=${isSearching}, previewUrl=${previewUrl}, selectedFile=${selectedFile?.name}`
  );

  return (
    <div
      className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow sticky top-[calc(6rem+6rem)] mt-6" // Adjust top/mt as needed
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="flex flex-col items-center border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md p-4 text-center mb-3">
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
          className="hidden" // Hide default input
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
          {selectedFile ? "Change Image" : "Upload Image"}
        </label>
        {!selectedFile && (
          <p className="text-xs text-gray-500 mt-1">or drag & drop</p>
        )}
      </div>

      <button
        onClick={handleImageSearch}
        disabled={!selectedFile || isSearching}
        className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
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

      {searchError && (
        <p className="text-xs text-red-500 mt-2 text-center">
          Error: {searchError}
        </p>
      )}
    </div>
  );
}
