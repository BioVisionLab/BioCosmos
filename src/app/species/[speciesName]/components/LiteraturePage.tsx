"use client";

import { CrossRefAttribution, CrossRefLink } from "@/components/Attribution";
import Info from "@/components/Info";
import { TextLoading } from "@/components/Loadings";
import { NoData } from "@/components/NoData";
import {
  CrossRefResult,
  LiteratureResult,
  PublicationsByYear,
  fetchLiterature,
} from "@/lib/crossref";
import Link from "next/link";
import { JSX, useEffect, useState } from "react";

interface LiteraturePageProps {
  speciesName: string;
}

export function LiteraturePage({ speciesName }: LiteraturePageProps) {
  // Keyed by the species it was fetched for, so a change of species reads as
  // loading without resetting state synchronously inside the effect.
  const [result, setResult] = useState<{
    speciesName: string;
    literature: LiteratureResult | null;
  } | null>(null);

  useEffect(() => {
    // The tab can mount before the species data arrives; wait for a name.
    if (!speciesName.trim()) return;
    let isMounted = true;
    fetchLiterature(speciesName)
      .then((literature) => {
        if (isMounted) setResult({ speciesName, literature });
      })
      .catch((error) => {
        console.error("Error fetching literature data:", error);
        if (isMounted) setResult({ speciesName, literature: null });
      });
    return () => {
      isMounted = false;
    };
  }, [speciesName]);

  const loading = result?.speciesName !== speciesName;
  const literature = loading ? null : result.literature;
  const failed = !loading && literature === null;

  if (loading) {
    return (
      <div className="mx-auto items-center">
        <TextLoading msg="Loading literature data" />
      </div>
    );
  }

  if (failed || !literature) {
    return (
      <div className="mx-auto items-center">
        <NoData text="Literature could not be loaded right now. Please try again later." />
      </div>
    );
  }

  const {
    acceptedName,
    genus,
    synonymsSearched,
    species,
    speciesCount,
    genusRelated,
    genusRelatedCount,
    partial,
  } = literature;

  if (speciesCount === 0 && genusRelatedCount === 0) {
    return (
      <div className="mx-auto items-center">
        <NoData text="No relevant literature found since 1995." />
        {partial ? <PartialNotice /> : null}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <Info>
          <p>
            This literature list is automatically fetched from <CrossRefLink />{" "}
            and kept only when the title or abstract matches the taxon name. It
            may still contain irrelevant publications.
          </p>
        </Info>
        {partial ? <PartialNotice /> : null}
      </div>

      {speciesCount > 0 ? (
        <section aria-labelledby="literature-species" className="mb-8">
          <h2 id="literature-species" className="text-xl font-semibold mb-1">
            Publications on <em>{acceptedName}</em>{" "}
            <span className="text-base font-normal text-deep-mocha-500">
              ({speciesCount})
            </span>
          </h2>
          <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400 mb-2">
            Publications found for this species from about the past 30 years.
            {synonymsSearched.length > 0 ? (
              <>
                {" "}
                Searched under the accepted name <em>
                  {acceptedName}
                </em> and{" "}
                {synonymsSearched.length === 1
                  ? "an earlier name"
                  : `${synonymsSearched.length} earlier names`}
                : <NameList names={synonymsSearched} />.
              </>
            ) : null}
          </p>
          <PublicationsList publications={species} />
        </section>
      ) : null}

      {genusRelated && genus && genusRelatedCount > 0 ? (
        <section aria-labelledby="literature-genus" className="mb-6">
          <h2 id="literature-genus" className="text-xl font-semibold mb-1">
            Related literature on the genus <em>{genus}</em>{" "}
            <span className="text-base font-normal text-deep-mocha-500">
              ({genusRelatedCount})
            </span>
          </h2>
          <PublicationsList publications={genusRelated} />
        </section>
      ) : null}

      <CrossRefAttribution isLarge={true} />
    </div>
  );
}

function PartialNotice() {
  return (
    <p className="text-sm text-amber-700 dark:text-amber-400 mt-2">
      CrossRef did not answer every search, so this list may be incomplete. Try
      again in a few minutes.
    </p>
  );
}

/** Italic names joined by commas, e.g. "A, B and C". */
function NameList({ names }: { names: string[] }) {
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

function PublicationsList({
  publications,
}: {
  publications: PublicationsByYear;
}) {
  return (
    <div>
      {sortYearsDescending(publications).map(([year, items]) => (
        <div key={year} className="m-2">
          <h3 className="text-xl font-semibold text-pacific-blue-700 dark:text-pacific-blue-400">
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
              className="underline hover:text-pacific-blue-700"
            >
              {pub.doi}
            </Link>
          </span>
        ) : (
          ""
        )}
      </p>
      {pub.doi ? <JournalViewButton doi={pub.doi} /> : null}
    </div>
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

/* `doi` is already a resolvable https://doi.org/... URL. */
function JournalViewButton({ doi }: { doi: string }) {
  return (
    <div className="border border-pacific-blue-700 px-2 py-1 rounded-md w-fit mt-2 mb-4 hover:bg-pacific-blue-700 hover:text-white text-sm">
      <Link
        href={doi}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-2"
      >
        View Publication
      </Link>
    </div>
  );
}
