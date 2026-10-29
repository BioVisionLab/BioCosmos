"use client";

import { JSX } from "react";
import Link from "next/link";

import CopyButton from "@/components/CopyButton";
import {
  publicationTypeKey,
  publicationTypes,
} from "@/components/literature/publicationTypes";
import {
  CrossRefResult,
  PublicationsByYear,
  formatCitation,
} from "@/lib/crossref";

export function PartialNotice() {
  return (
    <p className="text-sm text-amber-700 dark:text-amber-400 mt-2">
      CrossRef did not answer every search, so this list may be incomplete. Try
      again in a few minutes.
    </p>
  );
}

/** Italic names joined by commas, e.g. "A, B and C". */
export function NameList({ names }: { names: string[] }) {
  return (
    <>
      {names.map((name, i) => (
        <span key={name}>
          {i > 0 ? (i === names.length - 1 ? " and " : ", ") : ""}
          <em>{name}</em>
        </span>
      ))}
    </>
  );
}

export function scrollToHeading(id: string) {
  document
    .getElementById(id)
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/** Works a list shows at first, and how many more each "Show more" adds. */
export const LITERATURE_PAGE_SIZE = 20;

function countWorks(publications: PublicationsByYear): number {
  return Object.values(publications).reduce(
    (total, items) => total + items.length,
    0,
  );
}

/** The newest `limit` works, still grouped by year. */
function newestWorks(
  publications: PublicationsByYear,
  limit: number,
): PublicationsByYear {
  const shown: PublicationsByYear = {};
  let remaining = limit;

  for (const [year, items] of sortYearsDescending(publications)) {
    if (remaining <= 0) break;

    shown[year] = items.slice(0, remaining);
    remaining -= shown[year].length;
  }

  return shown;
}

/** How many works a list must show for `year` to be on it in full. */
export function worksThrough(
  publications: PublicationsByYear,
  year: string,
): number {
  let total = 0;

  for (const [key, items] of sortYearsDescending(publications)) {
    total += items.length;

    if (key === year) break;
  }

  return total;
}

/**
 * A publication list that shows the newest works first and grows by
 * LITERATURE_PAGE_SIZE at a time. The limit is the caller's, so the summary
 * chart can grow the list to reach a year it links to.
 */
export function PagedPublications({
  publications,
  section,
  limit,
  onLimit,
}: {
  publications: PublicationsByYear;
  section: string;
  limit: number;
  onLimit: (limit: number) => void;
}) {
  const total = countWorks(publications);
  const more = Math.min(LITERATURE_PAGE_SIZE, total - limit);

  return (
    <div>
      <PublicationsList
        publications={newestWorks(publications, limit)}
        section={section}
      />
      {more > 0 ? (
        <div className="mx-2 mb-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => onLimit(limit + LITERATURE_PAGE_SIZE)}
            className={secondaryButtonClass}
          >
            Show {more} more
          </button>
          <span className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
            Showing {limit.toLocaleString("en-US")} of{" "}
            {total.toLocaleString("en-US")}
          </span>
        </div>
      ) : null}
    </div>
  );
}

function sortYearsDescending(publications: PublicationsByYear) {
  return Object.entries(publications).sort(([yearA], [yearB]) => {
    const a = parseInt(yearA, 10);
    const b = parseInt(yearB, 10);

    if (isNaN(a) && isNaN(b)) return 0;

    if (isNaN(a)) return 1;

    if (isNaN(b)) return -1;

    return b - a;
  });
}

export function PublicationsList({
  publications,
  section,
}: {
  publications: PublicationsByYear;
  /** Prefixes each year heading's id, which the summary chart links to. */
  section: string;
}) {
  return (
    <div>
      {sortYearsDescending(publications).map(([year, items]) => (
        <div key={year} className="m-2">
          <h3
            id={`literature-${section}-year-${year}`}
            className="scroll-mt-24 text-xl font-semibold text-pacific-blue-700 dark:text-pacific-blue-400"
          >
            {year}
          </h3>
          <div className="border-l-2 border-pacific-blue-500 mx-2 pl-4 pb-2">
            {items.map((pub, index) => (
              <Publication key={pub.doi ?? `${year}-${index}`} pub={pub} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function Publication({ pub }: { pub: CrossRefResult }) {
  return (
    <div>
      <PublicationTypeLabel type={pub.publicationType} />
      <JournalTitle title={pub.title} />
      {pub.matchedVia === "synonym" && pub.matchedName ? (
        <p className="text-xs text-hunter-green-700 dark:text-hunter-green-400 mb-1">
          Published as <em>{pub.matchedName}</em>
        </p>
      ) : null}
      {pub.mentions.length > 0 ? (
        <p className="text-xs text-hunter-green-700 dark:text-hunter-green-400 mb-1">
          Mentions <NameList names={pub.mentions} />
        </p>
      ) : null}
      <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400 mb-1">
        {pub.authors.join(", ")}.{" "}
        {pub.published_year ? ` (${pub.published_year}). ` : ""}
        <span className="italic">{pub.journal}</span>
        {pub.volume ? `, ${pub.volume}` : ""}
        {pub.issue ? ` (${pub.issue})` : ""}
        {pub.pages ? `, pp. ${pub.pages}` : ""}.
        {pub.doi ? (
          <span>
            {" "}
            <Link
              href={pub.doi}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
            >
              {pub.doi}
            </Link>
          </span>
        ) : (
          ""
        )}
      </p>
      <div className="flex flex-wrap items-center gap-2 mt-2 mb-4">
        {pub.doi ? <JournalViewButton doi={pub.doi} /> : null}
        <CopyButton
          text={formatCitation(pub)}
          label="Copy citation"
          buttonText="Copy Citation"
          className={secondaryButtonClass}
        />
      </div>
    </div>
  );
}

function PublicationTypeLabel({ type }: { type?: string }) {
  if (!type) return null;

  const { label, fill, text } = publicationTypes[publicationTypeKey(type)];

  return (
    <span
      className={`inline-block rounded px-2 py-0.5 mb-1 text-xs font-semibold ${fill} ${text}`}
    >
      {label}
    </span>
  );
}

/*
Show title in standard format but detect italic tags for species names
*/
function JournalTitle({ title }: { title: string }) {
  return (
    <p className="font-medium text-lg">
      {(() => {
        const parts: (string | JSX.Element)[] = [];
        // Publishers mark italics with <i>, <em> or JATS <italic>.
        const regex = /<(i|em|italic)>(.*?)<\/\1>/gi;
        let lastIndex = 0;
        let match: RegExpExecArray | null;
        let k = 0;

        while ((match = regex.exec(title)) !== null) {
          if (match.index > lastIndex) {
            parts.push(title.slice(lastIndex, match.index));
          }

          parts.push(<em key={`i-${k++}`}>{match[2]}</em>);
          lastIndex = regex.lastIndex;
        }

        if (lastIndex < title.length) {
          parts.push(title.slice(lastIndex));
        }

        return parts.length ? parts : title;
      })()}
    </p>
  );
}

const publicationButtonBase =
  "inline-flex items-center gap-1 border px-2 py-1 rounded-md text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pacific-blue-700 dark:focus-visible:outline-pacific-blue-300";

/* Primary: white on pacific-blue-700 is 6.3:1, on 800 (hover) 10.5:1. */
const primaryButtonClass = `${publicationButtonBase} border-pacific-blue-700 bg-pacific-blue-700 font-medium text-white hover:border-pacific-blue-800 hover:bg-pacific-blue-800`;

const secondaryButtonClass = `${publicationButtonBase} border-pacific-blue-700 text-pacific-blue-700 hover:bg-pacific-blue-700/10 dark:border-pacific-blue-300 dark:text-pacific-blue-300 dark:hover:bg-pacific-blue-300/10`;

/* `doi` is already a resolvable https://doi.org/... URL. */
function JournalViewButton({ doi }: { doi: string }) {
  return (
    <Link
      href={doi}
      target="_blank"
      rel="noopener noreferrer"
      className={primaryButtonClass}
    >
      View Publication
    </Link>
  );
}
