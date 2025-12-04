"use client"; // Mark this component as a Client Component

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { getSpeciesList } from "@/lib/speciesList";
import { fetchSpeciesThumbnail } from "@/lib/images";
import Link from "next/link";
import SearchSwitcher from "./SearchSwitcher";
import { ImageLoading } from "./Loadings";
import { cleanSpeciesName } from "@/lib/names";
import { ButterflyAiIcon } from "./ui/Butterfly";
import { isBackendAlive } from "@/lib/backend";

function SpeciesThumbnail({
  species,
  index,
}: {
  species: string;
  index: number;
}) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);

  useEffect(() => {
    const fetchThumbnail = async () => {
      try {
        const thumbnailUrl = await fetchSpeciesThumbnail(species);
        setThumbnailUrl(thumbnailUrl);
      } catch (error) {
        console.error("Failed to fetch species thumbnail:", error);
      }
    };

    fetchThumbnail();
  }, [species]);

  let linkUrl = thumbnailUrl ? `/species/${species}` : "#";
  const speciesName = cleanSpeciesName(species);
  return (
<<<<<<< HEAD
    <div className="w-fit h-fit justify-center bg-gray-100 dark:bg-gray-700 rounded-2xl items-center text-center p-4">
=======
    <div className="w-fit h-fit justify-center bg-gray-200 dark:bg-gray-700 rounded-2xl items-center text-center p-4">
>>>>>>> api-redesign
      <Link key={index} href={linkUrl}>
        {thumbnailUrl ? (
          <>
            <Image
              src={thumbnailUrl}
              alt={`Species Thumbnail ${index + 1}`}
              width={150}
              height={150}
              className="mx-auto object-contain"
            />
            <h2
              className="text-sm truncate italic text-center text-gray-400"
              title={speciesName}
            >
              {speciesName}
            </h2>
          </>
        ) : (
          <ImageLoading size={150} />
        )}
      </Link>
    </div>
  );
}

export default function HomePage() {
  return (
    <div className="flex flex-col items-center min-h-screen">
      <ButterflyAiIcon className="w-24 h-24 fill-emerald-400" />
      <div className="mt-2 mb-6 text-center">
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight font-serif bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-transparent bg-clip-text drop-shadow">
          BioCosmos
        </h1>
        <p className="mt-3 text-base sm:text-lg text-gray-600 dark:text-gray-300">
          Discover species & traits with AI: fast, visual, and intelligent
          search
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

      <HomeContent />
    </div>
  );
}

function HomeContent() {
  const [backendAlive, setBackendAlive] = useState<boolean | null>(null);

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const alive = await isBackendAlive();
        setBackendAlive(alive);
      } catch (error) {
        console.error("Failed to check backend status:", error);
        setBackendAlive(false);
      }
    };

    checkBackend();
  }, []);

  if (backendAlive === null) {
    return (
      <div className="mt-12">
        <ImageLoading size={240} msg="Connecting to backend" />
      </div>
    );
  }

  if (backendAlive === false) {
    return (
      <div className="mt-12">
        <p className="text-red-600 dark:text-red-400">
          Unable to connect to the backend service. Please try again later.
        </p>
      </div>
    );
  }
  const speciesList = getSpeciesList();
  return (
    <div>
      <SearchSwitcher />
      <div className="w-full max-w-5xl mt-12 mb-4 px-4 mx-auto">
        <div className="flex items-center gap-3">
          <span className="h-px flex-1 bg-gradient-to-r rounded-full from-emerald-400/50 via-teal-400/50 to-cyan-400/50" />
          <h2 className="text-xs sm:text-sm font-semibold tracking-wider uppercase text-emerald-600 dark:text-emerald-300 flex items-center gap-2">
            <span className="text-lg">🦋</span>
            Featured Butterflies
          </h2>
          <span className="h-px flex-1 bg-gradient-to-r rounded-full from-emerald-400/50 via-teal-400/50 to-cyan-400/50" />
        </div>
        <p className="mt-3 text-center text-sm sm:text-base text-gray-600 dark:text-gray-400">
          Get started with a curated list of butterflies.
        </p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mx-auto">
        {speciesList.map((species, index) => (
          <SpeciesThumbnail key={index} species={species} index={index} />
        ))}
      </div>
    </div>
  );
}
