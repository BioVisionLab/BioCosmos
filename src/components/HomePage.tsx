"use client"; // Mark this component as a Client Component

import { useState, useEffect, useMemo, type ReactNode } from "react";
import { getSpeciesList } from "@/lib/speciesList";
import { speciesThumbnailUrl } from "@/lib/images";
import SearchSwitcher from "./SearchSwitcher";
import { ImageLoading } from "./Loadings";
import SpeciesTile from "./SpeciesTile";
import LandingSectionHeading, {
  LANDING_CONTAINER,
  LANDING_GRID,
} from "./LandingSection";
import { cleanSpeciesName, speciesUrlFromName } from "@/lib/names";
import { isBackendAlive } from "@/lib/backend";
import Logo from "./Logo";
import ColorSearch from "./ColorSearch";
import { ButterflyIcon } from "./ui/icons";

/**
 * @param dataSummary The collection summary, rendered on the server and
 *   passed in as a slot so this client component does not have to fetch it.
 */
export default function HomePage({
  dataSummary,
}: {
  dataSummary?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center min-h-screen">
      <div className="mt-10 sm:mt-12 mb-6 text-center">
        <div className="flex justify-center mb-2">
          <h1 className="sr-only">Lepiverse</h1>
          <Logo className="w-64 sm:w-80 md:w-96" />
        </div>
        <p className="text-base sm:text-md text-deep-mocha-600 dark:text-deep-mocha-300">
          A BioCosmos portal for Lepidoptera, featuring all butterfly families.
        </p>
        <p className="mt-8 text-base sm:text-lg text-deep-mocha-600 dark:text-deep-mocha-300 max-w-3xl mx-auto text-balance">
          BioCosmos is an image-based web platform that combines conventional biodiversity database with computer vision and natural language processing to reveal hidden patterns in organism coloration and simplify querying large-scale biological data.
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

      <HomeContent dataSummary={dataSummary} />
      {/* spacer between homepage content and the site footer */}
      <div className="h-8 md:h-14 lg:h-16" aria-hidden="true" />
    </div>
  );
}

function HomeContent({ dataSummary }: { dataSummary?: ReactNode }) {
  const [backendAlive, setBackendAlive] = useState<boolean | null>(null);

  // Chosen once per mount. `getSpeciesList()` shuffles, so calling it from
  // the render body swapped the featured six on every re-render — including
  // the re-render that resolves the backend check.
  const speciesList = useMemo(() => getSpeciesList(), []);

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

  return (
    <div className="w-full">
      <SearchSwitcher />

      <LandingSectionHeading
        className="mt-12"
        icon={<ButterflyIcon />}
        title="Featured Butterflies"
        description="Get started with a curated list of butterflies."
      />
      <div className={`${LANDING_GRID} ${LANDING_CONTAINER}`}>
        {speciesList.map((species, index) => (
          <SpeciesThumbnail key={species} species={species} index={index} />
        ))}
      </div>

      <ColorSearch />
      {dataSummary}
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
  // No state and no effect: the thumbnail URL is a pure function of the
  // name, so fetching it asynchronously only bought a guaranteed first
  // render with no image — six of them, every visit.
  return (
    <SpeciesTile
      href={`/species/${speciesUrlFromName(species)}`}
      imageUrl={speciesThumbnailUrl(species)}
      label={cleanSpeciesName(species)}
      alt={`Species Thumbnail ${index + 1}`}
    />
  );
}
