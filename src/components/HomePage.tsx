"use client"; // Mark this component as a Client Component

import { useState, useEffect, type ReactNode } from "react";
import Link from "next/link";
import SearchSwitcher from "./SearchSwitcher";
import { ImageLoading } from "./Loadings";
import LandingSectionHeading, { LANDING_CONTAINER } from "./LandingSection";
import { isBackendAlive } from "@/lib/backend";
import Logo from "./Logo";
import ColorSearch from "./ColorSearch";
import { ButterflyIcon, NetworkIcon, TaxonomyIcon } from "./ui/icons";

interface HomeSlots {
  specimenTray?: ReactNode;
  featured?: ReactNode;
  familyExplorer?: ReactNode;
  dataSummary?: ReactNode;
  countryDiversity?: ReactNode;
}

/**
 * Every data-bearing section is rendered on the server and passed in as a
 * slot, so this client component does not have to fetch it.
 *
 * @param specimenTray The hero's tray of the day's featured specimens.
 * @param featured The featured species rail, the rest of the same sample.
 * @param familyExplorer The tray of families, one specimen each.
 * @param dataSummary The collection summary band.
 * @param countryDiversity The species-by-country map section.
 *
 * The root is an inline-size container: the hero and the summary band break
 * out to the screen edge by measuring against it (`bc-bleed`).
 */
export default function HomePage({
  specimenTray,
  featured,
  familyExplorer,
  dataSummary,
  countryDiversity,
}: HomeSlots) {
  return (
    <div className="@container flex w-full min-h-screen flex-col">
      <Hero specimenTray={specimenTray} />
      <HomeContent
        featured={featured}
        familyExplorer={familyExplorer}
        dataSummary={dataSummary}
        countryDiversity={countryDiversity}
      />
      {/* spacer between homepage content and the site footer */}
      <div className="h-8 md:h-14 lg:h-16" aria-hidden="true" />
    </div>
  );
}

/**
 * What the collection is, in three chips — not what it can do.
 *
 * The search modes are named on the tab strip right above them, so these are
 * the claims nothing else in the hero makes.
 *
 * Outlined, each with a small line icon from the shared set, so they sit
 * under the search as annotations rather than competing with it.
 */
const CREDENTIALS = [
  { label: "Every butterfly family", Icon: ButterflyIcon },
  { label: "Harmonized taxonomy", Icon: TaxonomyIcon },
  { label: "Advanced machine learning", Icon: NetworkIcon },
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
 * The top of the landing page, as a collection drawer: the copy and the
 * search on the left, on millimetre graph paper, and a unit tray of the day's
 * featured specimens on the right.
 *
 * The band runs the full width of the screen (`bc-bleed`), and on a desktop
 * the tray runs on past the column to the screen's right edge, like a drawer
 * pulled half out. The grid is itself an inline-size container so the tray
 * can measure exactly how far that is.
 *
 * The headline's two key phrases carry the green and the blue of the brand
 * with a soft underline (`bc-key`); the lead sets the method in bold. That is
 * all the emphasis the hero has, so it lands on what the site is about.
 *
 * `bc-rise` staggers the blocks in on load, and the tray's specimens settle
 * into their compartments as their images arrive; both stand down under
 * `prefers-reduced-motion`.
 */
function Hero({ specimenTray }: { specimenTray?: ReactNode }) {
  return (
    <section
      className="bc-bleed bc-graph-paper -mt-4 border-b border-deep-mocha-200/80 dark:border-deep-mocha-800"
      aria-label="Lepiverse"
    >
      <div className="[padding-inline:var(--bc-gutter)]">
        <div
          className={`${LANDING_CONTAINER} @container grid items-center gap-10 py-10 sm:py-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.08fr)] lg:gap-14 lg:py-16`}
        >
          <div className="flex min-w-0 flex-col items-start gap-6">
            <h1 className="bc-rise">
              <span className="sr-only">Lepiverse</span>
              <Logo className="w-44 sm:w-52" />
            </h1>

            <p
              className="bc-rise font-display text-[clamp(2rem,1.25rem+2.8vw,3.4rem)] font-semibold leading-[1.08] tracking-tight text-balance text-deep-mocha-900 dark:text-deep-mocha-50"
              style={{ animationDelay: "90ms" }}
            >
              Explore <em className="bc-key">butterfly diversity</em> and their
              fascinating <em className="bc-key bc-key-blue">coloration</em>
            </p>

            <p
              className="bc-rise max-w-xl text-base leading-relaxed text-deep-mocha-600 sm:text-lg dark:text-deep-mocha-300"
              style={{ animationDelay: "180ms" }}
            >
              Built from{" "}
              <strong className="font-semibold text-deep-mocha-900 dark:text-deep-mocha-50">
                curated natural history records
              </strong>{" "}
              and{" "}
              <strong className="font-semibold text-deep-mocha-900 dark:text-deep-mocha-50">
                modern machine learning
              </strong>
              . We clean, validate, and harmonize records from museums and
              aggregators, and use computer vision to extract traits and
              patterns from specimen images.
            </p>

            {/* relative z-10: bc-rise leaves a transform behind, which makes
                this a stacking context, and without a z-index the chips
                below would paint over the open "Search by" list. */}
            <div
              className="bc-rise relative z-10 w-full"
              style={{ animationDelay: "240ms" }}
            >
              <SearchSwitcher align="start" className="mt-1" />
            </div>

            <ul
              className="bc-rise -mt-4 flex flex-wrap gap-2"
              style={{ animationDelay: "300ms" }}
            >
              {CREDENTIALS.map(({ label, Icon }) => (
                <li
                  key={label}
                  className="inline-flex items-center gap-2 rounded-full border border-deep-mocha-200 bg-white/60 px-3 py-1 text-xs text-deep-mocha-700 backdrop-blur sm:text-sm dark:border-deep-mocha-700 dark:bg-deep-mocha-900/40 dark:text-deep-mocha-300"
                >
                  <Icon size="sm" className="h-4 w-4 shrink-0" />
                  {label}
                </li>
              ))}
            </ul>
          </div>

          <div
            className="bc-rise min-w-0 lg:mr-[calc(50cqw-50vw)]"
            style={{ animationDelay: "120ms" }}
          >
            {specimenTray}
          </div>
        </div>
      </div>
    </section>
  );
}

function HomeContent({
  featured,
  familyExplorer,
  dataSummary,
  countryDiversity,
}: Omit<HomeSlots, "specimenTray">) {
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
      <div className="mt-12 flex justify-center">
        <ImageLoading size={240} msg="Connecting to BioCosmos" />
      </div>
    );
  }

  if (backendAlive === false) {
    return (
      <div className="mt-12 text-center flex flex-col items-center px-4">
        <p className="text-burnt-peach-600 dark:text-burnt-peach-400 mb-2">
          Unable to connect to BioCosmos.
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
    // An inline-size container too, for the summary band's breakout.
    <div className="@container w-full">
      <section className="mt-16 sm:mt-20" aria-labelledby="featured-heading">
        <LandingSectionHeading
          id="featured-heading"
          eyebrow="Featured species"
          title="Browse featured butterflies"
          description="A sample of the species with the most complete records (updated daily)."
          className="bc-reveal"
        />
        {/* Its own container, so the rail's breakout lines its first card
            up with this column rather than the page's. */}
        <div className={`${LANDING_CONTAINER} @container`}>{featured}</div>
      </section>

      <ColorSearch />
      {familyExplorer}
      {dataSummary}
      {countryDiversity}
      <Acknowledgments />
    </div>
  );
}

/**
 * The closing note: the collection exists because museums digitized their
 * drawers and curators keep the names behind them straight. Last on the page
 * so it reads as a sign-off, and pointed at the collections page, where the
 * holding institutions and aggregators are credited by name.
 */
function Acknowledgments() {
  return (
    <section
      className={`${LANDING_CONTAINER} bc-reveal mt-20`}
      aria-labelledby="acknowledgments-heading"
    >
      <div className="rounded-3xl border border-deep-mocha-200 bg-white/60 p-6 sm:p-8 dark:border-deep-mocha-700 dark:bg-deep-mocha-800/40">
        <LandingSectionHeading
          id="acknowledgments-heading"
          eyebrow="Acknowledgments"
          title="Thank you"
          contained={false}
          className="mb-3"
        />
        <p className="max-w-3xl text-sm sm:text-base leading-relaxed text-deep-mocha-700 dark:text-deep-mocha-300">
          This website would not be possible without the natural history museums
          that care for and digitize their collections, the taxonomic curators
          whose expertise keeps every name accurate, and all the contributors
          who share their specimens, images, and records with the world. Thank
          you.
        </p>
        <p className="mt-3 text-sm">
          <Link
            href="/collections"
            className="text-pacific-blue-600 dark:text-pacific-blue-400 hover:underline"
          >
            See our data contributors →
          </Link>
        </p>
      </div>
    </section>
  );
}
