"use client";

import { CrossRefAttribution, CrossRefLink } from "@/components/Attribution";
import { TextLoading } from "@/components/Loadings";
import { NoData } from "@/components/NoData";
import { CrossRefResult, fetchCrossRefData } from "@/lib/crossref";
import Link from "next/link";
import { JSX, useEffect, useState } from "react";

interface LiteraturePageProps {
  speciesName: string;
}

export function LiteraturePage({ speciesName }: LiteraturePageProps) {
  const [relevantLiterature, setRelevantLiterature] = useState<
    Record<string, CrossRefResult[]>
  >({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    const fetchData = async () => {
      try {
        const data = await fetchCrossRefData(speciesName);
        if (isMounted) {
          setRelevantLiterature(data);
        }
      } catch (error) {
        console.error("Error fetching literature data:", error);
        if (isMounted) {
          setRelevantLiterature({});
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };
    fetchData();
    return () => {
      isMounted = false;
    };
  }, [speciesName]);

  if (loading) {
    return (
      <div className="mx-auto items-center">
        <TextLoading text="Loading literature data" />
      </div>
    );
  }

  if (Object.keys(relevantLiterature).length === 0) {
    return (
      <div className="mx-auto items-center">
        <NoData text="No relevant literature found for the past 20 years." />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <p className="rounded-md border border-yellow-200 bg-yellow-50 px-4 py-3 text-[11px] leading-snug text-gray-700 w-fit">
          This literature list is automatically fetched from{" "}
          <span>
            <CrossRefLink />
          </span>{" "}
          and has not been manually reviewed; it may contain irrelevant
          publications.
        </p>
      </div>
      <div className="mb-2">
        <p className="text-xl font-semibold mb-2">
          Found {Object.values(relevantLiterature).flat().length} publications
        </p>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Publications are sorted by year and relevance to the species. Limited
          to 50 most relevant publications from the past ~20 years.
        </p>
      </div>
      <div>
        {Object.entries(relevantLiterature)
          .sort(([yearA], [yearB]) => {
            const a = parseInt(yearA, 10);
            const b = parseInt(yearB, 10);
            if (isNaN(a) && isNaN(b)) return 0;
            if (isNaN(a)) return 1;
            if (isNaN(b)) return -1;
            return b - a;
          })
          .map(([year, publications]) => (
            <div key={year} className="m-2">
              <h3 className="text-xl font-semibold text-teal-700 dark:text-teal-400">
                {year}
              </h3>
              <div className="border-l-2 border-teal-500 mx-2 pl-4 pb-2">
                {publications.map((pub, index) => (
                  <div key={index} className="">
                    <JournalTitle title={pub.title} />
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
                      {pub.authors.join(", ")}.{" "}
                      <span className="italic">{pub.journal}</span>
                      {pub.volume ? `, Vol. ${pub.volume}` : ""}
                      {pub.issue ? `, No. ${pub.issue}` : ""}
                      {pub.pages ? `, pp. ${pub.pages}` : ""}.
                      {pub.published_year ? ` (${pub.published_year}).` : ""}
                      {pub.doi ? (
                        <span>
                          {" "}
                          <Link
                            href={pub.doi}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="underline hover:text-teal-700"
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
                ))}
              </div>
            </div>
          ))}
      </div>
      <CrossRefAttribution isLarge={true} />
    </div>
  );
}

/*
Show title in standard format but detect italic tags for species names
*/
function JournalTitle({ title, doi }: { title: string; doi?: string }) {
  return (
    <p className="font-medium text-lg">
      {(() => {
        const parts: (string | JSX.Element)[] = [];
        const regex = /<i>(.*?)<\/i>/gi;
        let lastIndex = 0;
        let match: RegExpExecArray | null;
        let k = 0;

        while ((match = regex.exec(title)) !== null) {
          if (match.index > lastIndex) {
            parts.push(title.slice(lastIndex, match.index));
          }
          parts.push(<em key={`i-${k++}`}>{match[1]}</em>);
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

function JournalViewButton({ doi }: { doi: string }) {
  return (
    <div
      key={doi}
      className="border border-teal-700 px-2 py-1 rounded-md w-fit mt-2 mb-4 hover:bg-teal-700 hover:text-white text-sm"
    >
      <Link
        href={`https://doi.org/${doi}`}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-2"
      >
        View Publication
      </Link>
    </div>
  );
}
