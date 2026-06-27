"use client"; // Mark this component as a Client Component

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { getSpeciesList } from "@/lib/speciesList";
import { fetchSpeciesThumbnail } from "@/lib/images";
import Link from "next/link";
import SearchSwitcher from "./SearchSwitcher";
import { ImageLoading } from "./Loadings";
import { cleanSpeciesName, speciesUrlFromName } from "@/lib/names";
import { isBackendAlive } from "@/lib/backend";
import Logo from "./Logo";

export default function HomePage() {
  return (
    <div className="flex flex-col items-center min-h-screen">
      <div className="mt-12 mb-6 text-center">
        <div className="flex justify-center mb-2">
          <h1 className="sr-only">Lepiverse</h1>
          <Logo className="w-64 sm:w-80 md:w-96" />
        </div>
        <p className="text-base sm:text-md text-deep-mocha-600 dark:text-deep-mocha-300">
          A BioCosmos portal for Lepidoptera, featuring all butterfly families.
        </p>
        <p className="mt-8 text-base sm:text-lg text-deep-mocha-600 dark:text-deep-mocha-300 max-w-3xl mx-auto">
          BioCosmos uses computer vision and natural language processing to
          analyze wing patterns, synthesize scientific records, and unlock
          insights into species evolution.
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-2 text-xs sm:text-sm">
          <span className="px-3 py-1 rounded-full bg-hunter-green-100 dark:bg-hunter-green-900/40 text-hunter-green-700 dark:text-hunter-green-300">
            Image Search
          </span>
          <span className="px-3 py-1 rounded-full bg-frozen-water-100 dark:bg-frozen-water-900/40 text-frozen-water-700 dark:text-frozen-water-300">
            Smart Text Query
          </span>
          <span className="px-3 py-1 rounded-full bg-pacific-blue-100 dark:bg-pacific-blue-900/40 text-pacific-blue-700 dark:text-pacific-blue-300">
            Open Biodiversity Data
          </span>
        </div>
      </div>

      <HomeContent />
      {/* spacer between homepage content and the site footer */}
      <div className="h-8 md:h-14 lg:h-16" aria-hidden="true" />
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
      <div className="mt-12 text-center flex flex-col items-center px-4">
        <p className="text-burnt-peach-600 dark:text-burnt-peach-400 mb-2">
          Unable to connect to the backend service.
        </p>
        <p className="text-deep-mocha-600 dark:text-deep-mocha-400 text-sm max-w-md">
          This usually occurs during website updates (approx. 3-15 minutes
          downtime). Please close this page and try again later. If the issue
          persists for more than 15 minutes, please{" "}
          <a
            href="https://github.com/BioVisionLab/BioCosmos/issues"
            target="_blank"
            rel="noopener noreferrer"
            className="text-pacific-blue-600 dark:text-pacific-blue-400 hover:underline"
          >
            file an issue on GitHub
          </a>
          .
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
          <span className="h-px flex-1 bg-gradient-to-r rounded-full from-hunter-green-400/50 via-pacific-blue-400/50 to-frozen-water-400/50" />
          <h2 className="text-xs sm:text-sm font-semibold tracking-wider uppercase text-hunter-green-600 dark:text-hunter-green-300 flex items-center gap-2">
            <span className="text-lg">🦋</span>
            Featured Butterflies
          </h2>
          <span className="h-px flex-1 bg-gradient-to-r rounded-full from-hunter-green-400/50 via-pacific-blue-400/50 to-frozen-water-400/50" />
        </div>
        <p className="mt-3 text-center text-sm sm:text-base text-deep-mocha-600 dark:text-deep-mocha-400">
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

  const linkUrl = thumbnailUrl
    ? `/species/${speciesUrlFromName(species)}`
    : "#";
  const speciesName = cleanSpeciesName(species);
  return (
    <Link
      key={index}
      href={linkUrl}
      className="w-full flex flex-col justify-center items-center text-center group"
    >
      {thumbnailUrl ? (
        <>
          <div className="relative w-full aspect-square bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-2xl p-4 overflow-hidden shadow-sm group-hover:shadow-md transition-shadow">
            <Image
              src={thumbnailUrl}
              alt={`Species Thumbnail ${index + 1}`}
              fill
              className="object-contain p-4"
              sizes="(max-width: 768px) 50vw, (max-width: 1200px) 25vw, 16vw"
              unoptimized
            />
          </div>
          <h2
            className="w-full text-sm truncate italic text-center text-deep-mocha-400 mt-2 px-1"
            title={speciesName}
          >
            {speciesName}
          </h2>
        </>
      ) : (
        <div className="w-full aspect-square flex flex-col items-center justify-center bg-deep-mocha-100 dark:bg-deep-mocha-800 rounded-2xl">
          <ImageLoading size={60} />
        </div>
      )}
    </Link>
  );
}
