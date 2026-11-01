"use client";

import { useEffect, useRef, useState } from "react";

import { CrossRefAttribution, CrossRefLink } from "@/components/Attribution";
import Info from "@/components/Info";
import {
  LiteratureSummary,
  type YearBin,
} from "@/components/literature/LiteratureSummary";
import {
  LITERATURE_PAGE_SIZE,
  PagedPublications,
  PartialNotice,
  scrollToHeading,
  worksThrough,
} from "@/components/literature/Publications";
import { TextLoading } from "@/components/Loadings";
import { NoData } from "@/components/NoData";
import { ITALIC_COL_RANKS } from "@/lib/colTaxonomy";
import {
  type HigherTaxonLiteratureResult,
  type HigherTaxonRank,
  fetchHigherTaxonLiterature,
} from "@/lib/crossref";

/**
 * Publications naming a taxon above species.
 *
 * Fetched on mount, and mounted only when the tab is first opened, so a page
 * view that never opens it never calls CrossRef. `onCount` hands the total
 * back to the tab label.
 */
export default function HigherTaxonLiterature({
  rank,
  name,
  context,
  onCount,
}: {
  rank: HigherTaxonRank;
  name: string;
  /**
   * Searched beside the name to keep out namesakes in other fields: the
   * family of a genus, or the genus of a subgenus.
   */
  context?: string | null;
  onCount?: (count: number) => void;
}) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "failed" }
    | { status: "loaded"; literature: HigherTaxonLiteratureResult }
  >({ status: "loading" });
  const [limit, setLimit] = useState(LITERATURE_PAGE_SIZE);
  // The year heading to scroll to once the list has grown to include it.
  // A ref, not state: it only tells the effect below what to do after the
  // render that shows the year, and must not cause a render of its own.
  const pendingJump = useRef<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    fetchHigherTaxonLiterature(rank, name, context)
      .then((literature) => {
        if (!isMounted) return;

        setState({ status: "loaded", literature });
        onCount?.(literature.count);
      })
      .catch((error) => {
        console.error("Error fetching literature data:", error);

        if (isMounted) setState({ status: "failed" });
      });

    return () => {
      isMounted = false;
    };
  }, [rank, name, context, onCount]);

  useEffect(() => {
    if (!pendingJump.current) return;

    scrollToHeading(pendingJump.current);
    pendingJump.current = null;
  }, [limit]);

  if (state.status === "loading") {
    return <TextLoading msg="Loading literature" />;
  }

  if (state.status === "failed") {
    return (
      <NoData text="Literature could not be loaded right now. Please try again later." />
    );
  }

  const { literature } = state;
  const since = literature.fromYear ? ` since ${literature.fromYear}` : "";
  const taxon = ITALIC_COL_RANKS.has(rank) ? (
    <em>{literature.name}</em>
  ) : (
    literature.name
  );

  if (literature.count === 0) {
    return (
      <div>
        <NoData text={`No publications on ${literature.name} found${since}.`} />
        {literature.partial ? <PartialNotice /> : null}
      </div>
    );
  }

  const jumpToBin = (bin: YearBin) => {
    const year = String(bin.years[0]);
    const needed = worksThrough(literature.works, year);
    const id = `literature-taxon-year-${year}`;

    if (needed <= limit) {
      scrollToHeading(id);

      return;
    }

    // Grow the list to hold the year, and scroll once it renders.
    pendingJump.current = id;
    setLimit(needed);
  };

  return (
    <div>
      <div className="mb-4">
        <Info>
          <p>
            Fetched automatically from <CrossRefLink /> and kept only when the
            title or abstract names {taxon}
            {since}. It may still contain irrelevant publications.
          </p>
        </Info>
        {literature.partial ? <PartialNotice /> : null}
      </div>

      <LiteratureSummary
        lists={[literature.works]}
        onJumpToBin={jumpToBin}
        footer={
          <>
            {literature.count} naming {taxon}
          </>
        }
      />

      <PagedPublications
        publications={literature.works}
        section="taxon"
        limit={limit}
        onLimit={setLimit}
      />

      <CrossRefAttribution isLarge={true} />
    </div>
  );
}
