"use client"; // Mark this component as a Client Component

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { SpeciesThumbnails, getInitialSpeciesList } from "@/lib/speciesList";
import Link from "next/link";
import SearchSwitcher from "./SearchSwitcher";

export default function HomeClient() {
  const [speciesList, setSpeciesList] = useState<SpeciesThumbnails[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSpeciesThumbnails = async () => {
      try {
        const speciesList = await getInitialSpeciesList();
        setSpeciesList(speciesList);
      } catch (error) {
        console.error("Failed to fetch species thumbnails:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchSpeciesThumbnails();
  }, []); // Empty dependency array ensures this runs only once on mount

  return (
    <div className="flex flex-col items-center min-h-screen">
      <Image
        src="/leaflet/images/logo.png"
        alt="biocosmos logo"
        width={160}
        height={160}
      />
      <div className="mt-2 mb-6 text-center">
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight font-serif bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-transparent bg-clip-text drop-shadow">
          BioCosmos
        </h1>
        <p className="mt-3 text-base sm:text-lg text-gray-600 dark:text-gray-300">
          Discover species & traits with AI: fast, visual, and intelligent search
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-2 text-xs sm:text-sm">
          <span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">
            Image Search
          </span>
          <span className="px-3 py-1 rounded-full bg-cyan-100 dark:bg-cyan-900/40 text-cyan-700 dark:text-cyan-300">
            Smart Text Query
          </span>
          <span className="px-3 py-1 rounded-full bg-teal-100 dark:bg-teal-900/40 text-teal-700 dark:text-teal-300">
            Open Biodiversity Data
          </span>
        </div>
      </div>
      <SearchSwitcher />
      {loading ? (
        <p>Loading sample species...</p>
      ) : speciesList.length > 0 ? (
        <>
          <div className="w-full max-w-5xl mt-10 mb-4">
            <div className="flex items-center gap-3">
              <span className="h-px flex-1 bg-gradient-to-r from-emerald-400/50 via-teal-400/50 to-cyan-400/50" />
              <h2 className="text-xs sm:text-sm font-semibold tracking-wider uppercase text-emerald-600 dark:text-emerald-300 flex items-center gap-2">
                <span className="text-lg">🦋</span>
                Featured Butterflies
              </h2>
              <span className="h-px flex-1 bg-gradient-to-r from-emerald-400/50 via-teal-400/50 to-cyan-400/50" />
            </div>
            <p className="mt-3 text-center text-sm sm:text-base text-gray-600 dark:text-gray-400">
              Explore a few sample species to get started
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mx-auto">
            {speciesList.map((thumbnail, index) => (
              <Link key={index} href={`/species/${thumbnail.folderName}`}>
                <div className="flex flex-col items-center">
                  <div className="flex justify-center bg-gray-100 dark:bg-gray-700 rounded-2xl">
                    <Image
                      src={thumbnail.imageUrl}
                      alt={`Species Thumbnail ${index + 1}`}
                      width={150}
                      height={150}
                      className="m-2"
                    />
                  </div>
                  <div className="mt-2 text-center">
                    <h2
                      className="text-base truncate italic text-center text-gray-400"
                      title={thumbnail.name}
                    >
                      {thumbnail.name}
                    </h2>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </>
      ) : (
        <p>No species thumbnails available.</p>
      )}
    </div>
  );
}
