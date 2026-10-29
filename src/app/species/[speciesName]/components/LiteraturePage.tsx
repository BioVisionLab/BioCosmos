"use client";

import { CrossRefAttribution, CrossRefLink } from "@/components/Attribution";
import Info from "@/components/Info";
import {
  LiteratureSummary,
  type YearBin,
} from "@/components/literature/LiteratureSummary";
import {
  LITERATURE_PAGE_SIZE,
  NameList,
  PagedPublications,
  PartialNotice,
  scrollToHeading,
  worksThrough,
} from "@/components/literature/Publications";
import { TextLoading } from "@/components/Loadings";
import { NoData } from "@/components/NoData";
import { LiteratureResult, fetchLiterature } from "@/lib/crossref";
import { useEffect, useRef, useState } from "react";

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

  // How many works each list shows, keyed by the species like the result, so
  // another species starts from the first page again.
  const [shown, setShown] = useState<{
    speciesName: string;
    limits: Record<ListSection, number>;
  } | null>(null);
  const limits =
    shown?.speciesName === speciesName ? shown.limits : INITIAL_LIMITS;
  // The year heading to scroll to once the list has grown to include it.
  // A ref, not state: it only tells the effect below what to do after the
  // render that shows the year, and must not cause a render of its own.
  const pendingJump = useRef<string | null>(null);

  useEffect(() => {
    if (!pendingJump.current) return;

    scrollToHeading(pendingJump.current);
    pendingJump.current = null;
  }, [limits]);

  const setLimit = (section: ListSection, limit: number) =>
    setShown({ speciesName, limits: { ...limits, [section]: limit } });

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
    fromYear,
  } = literature;
  const since = fromYear ? ` since ${fromYear}` : "";

  if (speciesCount === 0 && genusRelatedCount === 0) {
    return (
      <div className="mx-auto items-center">
        <NoData text={`No relevant literature found${since}.`} />
        {partial ? <PartialNotice /> : null}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <Info>
          <p>
            This list of journal articles, datasets, books, preprints,
            proceedings, reports and dissertations is automatically fetched from{" "}
            <CrossRefLink /> and kept only when the title or abstract matches
            the taxon name. It may still contain irrelevant publications.
          </p>
        </Info>
        {partial ? <PartialNotice /> : null}
      </div>

      <SpeciesLiteratureSummary
        literature={literature}
        onJump={(section, year) => {
          const publications =
            section === "species" ? species : (genusRelated ?? {});
          const needed = worksThrough(publications, year);
          const id = `literature-${section}-year-${year}`;

          if (needed <= limits[section]) {
            scrollToHeading(id);

            return;
          }

          // Grow the list to hold the year, and scroll once it renders.
          pendingJump.current = id;
          setLimit(section, needed);
        }}
      />

      {speciesCount > 0 ? (
        <section aria-labelledby="literature-species" className="mb-8">
          <h2 id="literature-species" className="text-xl font-semibold mb-1">
            Publications on <em>{acceptedName}</em>{" "}
            <span className="text-base font-normal text-deep-mocha-500">
              ({speciesCount})
            </span>
          </h2>
          <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400 mb-2">
            Publications found for this species{since}.
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
          <PagedPublications
            publications={species}
            section="species"
            limit={limits.species}
            onLimit={(limit) => setLimit("species", limit)}
          />
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
          <PagedPublications
            publications={genusRelated}
            section="genus"
            limit={limits.genus}
            onLimit={(limit) => setLimit("genus", limit)}
          />
        </section>
      ) : null}

      <CrossRefAttribution isLarge={true} />
    </div>
  );
}

type ListSection = "species" | "genus";

const INITIAL_LIMITS: Record<ListSection, number> = {
  species: LITERATURE_PAGE_SIZE,
  genus: LITERATURE_PAGE_SIZE,
};

/*
The summary over both lists. A column jumps to its newest year under the
species when the species has papers in it, else under the genus.
*/
function SpeciesLiteratureSummary({
  literature,
  onJump,
}: {
  literature: LiteratureResult;
  onJump: (section: ListSection, year: string) => void;
}) {
  const speciesYears = Object.keys(literature.species);
  const synonymCount = Object.values(literature.species)
    .flat()
    .filter((pub) => pub.matchedVia === "synonym").length;

  const jumpToBin = (bin: YearBin) => {
    const speciesYear = bin.years.find((year) =>
      speciesYears.includes(String(year)),
    );

    if (speciesYear) onJump("species", String(speciesYear));
    else onJump("genus", String(bin.years[0]));
  };

  return (
    <LiteratureSummary
      lists={[literature.species, literature.genusRelated]}
      onJumpToBin={jumpToBin}
      footer={
        <>
          {literature.speciesCount} on the species
          {synonymCount > 0 ? ` (${synonymCount} under earlier names)` : ""}
          {literature.genus && literature.genusRelatedCount > 0 ? (
            <>
              {" "}
              · {literature.genusRelatedCount} on the genus{" "}
              <em>{literature.genus}</em>
            </>
          ) : null}
        </>
      }
    />
  );
}
