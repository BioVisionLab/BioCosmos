"use client"; // Mark this component as a Client Component

import { useState, useEffect, useMemo, type ReactNode } from "react";
import { getSpeciesList } from "@/lib/speciesList";
import { speciesImageUrl } from "@/lib/images";
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
export default function HomePage({ dataSummary }: { dataSummary?: ReactNode }) {
  return (
    <div className="flex flex-col items-center min-h-screen">
      <Hero />
      <HomeContent dataSummary={dataSummary} />
      {/* spacer between homepage content and the site footer */}
      <div className="h-8 md:h-14 lg:h-16" aria-hidden="true" />
    </div>
  );
}

/**
 * What the collection is, in three chips — not what it can do.
 *
 * The search modes are named on the tab strip a few hundred pixels below, so
 * listing them up here said the same thing twice before the reader had done
 * anything. These are the claims nothing else above the fold makes, and they
 * are what "museum-quality" means in practice.
 *
 * Outlined, with one small coloured dot each. The three saturated pills they
 * replace put more colour above the fold than the butterflies underneath it.
 */
const CREDENTIALS = [
  { label: "Every butterfly family", dot: "bg-hunter-green-500" },
  { label: "Harmonized taxonomy", dot: "bg-pacific-blue-500" },
  { label: "Open, citable records", dot: "bg-frozen-water-600" },
] as const;

/**
 * A hyphenated compound, kept on one line.
 *
 * `text-balance` is free to break at a hyphen that is already in the text, and
 * it did: the lead used to end a line on "image-" and open the next with
 * "based discovery". Which words land where still depends on the measure and
 * the loaded font, so this is marked on the compounds themselves rather than
 * dodged by picking a width that happens to break elsewhere today.
 *
 * Renders exactly the characters it is given; only the break opportunity
 * inside them is removed.
 */
function Compound({ children }: { children: string }) {
  return <span className="whitespace-nowrap">{children}</span>;
}

/**
 * The top of the landing page: the mark, one promise, one explanation.
 *
 * The copy used to be two paragraphs of the same weight, so neither led. Now
 * the first line is sized as the headline it actually is and the second gives
 * the mechanism beneath it.
 *
 * `bc-rise` staggers the three blocks in on load and `bc-hero-glow` washes a
 * soft gradient behind the mark; both sit in globals.css and both stand down
 * under `prefers-reduced-motion`.
 *
 * The section clips on the x axis only. The glow is wider than a phone screen,
 * so it must not add a horizontal scrollbar — but it also has to carry on up
 * behind the nav and off the top of the document instead of ending on this
 * section's top edge, which `overflow-hidden` drew as a hard line straight
 * across the page. `clip` on one axis leaves the other visible; `hidden` does
 * not.
 */
function Hero() {
  return (
    <section className="relative w-full overflow-x-clip px-4 pt-12 pb-2 sm:pt-16">
      <span className="bc-hero-glow" aria-hidden="true" />

      <div className="relative mx-auto flex max-w-3xl flex-col items-center text-center">
        <h1 className="bc-rise flex w-full justify-center">
          <span className="sr-only">Lepiverse</span>
          <Logo className="w-64 sm:w-80 md:w-96" />
        </h1>

        {/* 36rem, not the section's full width: 30 words at 2xl across 3xl
            filled three lines edge to edge, which reads as a paragraph set in
            headline size rather than as a headline. At this measure the three
            balanced lines come out nearly equal. */}
        <p
          className="bc-rise mt-7 max-w-3xl text-balance text-lg leading-snug tracking-tight text-deep-mocha-800 sm:text-xl dark:text-deep-mocha-100"
          style={{ animationDelay: "90ms" }}
        >
          Explore butterfly diversity and their fascinating coloration with a
          modern, museum-quality image platform.
        </p>

        {/* Narrower than the lead by one step. Sharing the lead's 36rem
            measure let this settle into two long lines whose widest ran 545px
            against the lead's 472px — the muted supporting sentence ended up
            visibly wider than the sentence it supports, which inverts the
            hierarchy. At 32rem it breaks into three short lines that sit well
            inside the block above. */}
        <p
          className="bc-rise mt-4 max-w-2xl text-balance text-sm leading-relaxed text-deep-mocha-600 sm:text-base dark:text-deep-mocha-400"
          style={{ animationDelay: "180ms" }}
        >
          The BioCosmos engine pairs curated biodiversity records with modern
          machine learning, revealing patterns in taxonomy, geography, and
          coloration. We develop data validation and harmonization methods and
          bring together disparate research-grade resources in on place, making
          them accessible to researchers, educators, and enthusiasts alike.
        </p>

        <ul
          className="bc-rise mt-8 flex flex-wrap justify-center gap-2"
          style={{ animationDelay: "270ms" }}
        >
          {CREDENTIALS.map(({ label, dot }) => (
            <li
              key={label}
              className="inline-flex items-center gap-2 rounded-full border border-deep-mocha-200 bg-white/60 px-3 py-1 text-xs text-deep-mocha-700 backdrop-blur sm:text-sm dark:border-deep-mocha-700 dark:bg-deep-mocha-900/40 dark:text-deep-mocha-300"
            >
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`}
                aria-hidden="true"
              />
              {label}
            </li>
          ))}
        </ul>
      </div>
    </section>
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
  // No state and no effect: the image URL is a pure function of the
  // name, so fetching it asynchronously only bought a guaranteed first
  // render with no image — six of them, every visit.
  return (
    <SpeciesTile
      href={`/species/${speciesUrlFromName(species)}`}
      imageUrl={speciesImageUrl(species)}
      label={cleanSpeciesName(species)}
      alt={`Species Thumbnail ${index + 1}`}
    />
  );
}
