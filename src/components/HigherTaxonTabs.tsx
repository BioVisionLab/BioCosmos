"use client";

import dynamic from "next/dynamic";
import {
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useId,
  useRef,
  useState,
} from "react";

import InstitutionDonut from "@/components/InstitutionDonut";
import { TextLoading } from "@/components/Loadings";
import type { HigherTaxonRank } from "@/lib/crossref";
import type { InstitutionShare } from "@/lib/higherTaxa";

// Code-split and mounted on first open, so a page view that never opens the
// tab never loads the list or calls CrossRef.
const HigherTaxonLiterature = dynamic(
  () => import("@/components/HigherTaxonLiterature"),
  {
    ssr: false,
    loading: () => <TextLoading msg="Loading literature" />,
  },
);

const TAB_IDS = ["classification", "specimens", "literature"] as const;

type TabId = (typeof TAB_IDS)[number];

const TAB_LABELS: Record<TabId, string> = {
  classification: "Classification",
  specimens: "Specimens",
  literature: "Literature",
};

/** The holder images with none on record are counted under. */
const UNKNOWN_INSTITUTION = "Unknown";

/*
The card and the open tab share one opaque surface and one border, which is
what joins them: the tab sits a pixel over the card's top edge and covers its
border there. A translucent surface would let that border show through.
*/
const SURFACE =
  "border-deep-mocha-200 bg-white dark:border-deep-mocha-700 dark:bg-deep-mocha-900";

function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

function plural(count: number, one: string, many: string): string {
  return `${formatCount(count)} ${count === 1 ? one : many}`;
}

/**
 * The classification, specimen holders and literature of a taxon above
 * species, one tab at a time.
 *
 * The classification arrives as `children`, rendered on the server: it is
 * the largest thing on the page, and passing it through keeps it out of this
 * component's hydration and in the HTML a crawler reads. Its panel is only
 * hidden, never unmounted, so the tree keeps whatever a reader expanded.
 */
export default function HigherTaxonTabs({
  rank,
  name,
  context,
  classificationCount,
  memberLabel,
  imageCount,
  institutions,
  controls,
  children,
}: {
  rank: HigherTaxonRank;
  name: string;
  /**
   * The taxon its literature search runs beside: a genus's family, or a
   * subgenus's genus.
   */
  context?: string | null;
  /** The members the tree lists, for the tab's badge. */
  classificationCount: number | null;
  /** What those members are, in the plural: "families", "genera", "species". */
  memberLabel: string;
  imageCount: number;
  institutions: InstitutionShare[];
  /** Shown beside the tabs while the classification is open. */
  controls?: ReactNode;
  children: ReactNode;
}) {
  const baseId = useId();
  const [active, setActive] = useState<TabId>("classification");
  // The literature panel stays mounted once opened, so switching back to it
  // does not search CrossRef again.
  const [literatureOpened, setLiteratureOpened] = useState(false);
  const [literatureCount, setLiteratureCount] = useState<number | null>(null);
  const tabRefs = useRef<Partial<Record<TabId, HTMLButtonElement | null>>>({});

  const select = useCallback((id: TabId) => {
    setActive(id);

    if (id === "literature") setLiteratureOpened(true);
  }, []);

  // Arrow keys move between tabs, as the ARIA tabs pattern expects.
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = TAB_IDS.indexOf(active);
    let next: number | null = null;

    if (event.key === "ArrowRight") next = (index + 1) % TAB_IDS.length;

    if (event.key === "ArrowLeft") {
      next = (index - 1 + TAB_IDS.length) % TAB_IDS.length;
    }

    if (event.key === "Home") next = 0;

    if (event.key === "End") next = TAB_IDS.length - 1;

    if (next === null) return;

    event.preventDefault();
    select(TAB_IDS[next]);
    tabRefs.current[TAB_IDS[next]]?.focus();
  };

  const badges: Record<TabId, number | null> = {
    classification: classificationCount,
    specimens: imageCount,
    literature: literatureCount,
  };

  const holders = institutions.filter(
    (share) => share.code !== UNKNOWN_INSTITUTION,
  ).length;
  // The line at the top of the card, saying what the open tab holds.
  const summaries: Record<TabId, string> = {
    classification:
      classificationCount === null
        ? "As classified by Catalogue of Life"
        : `${formatCount(classificationCount)} ${memberLabel} with images, as classified by Catalogue of Life`,
    specimens: holders
      ? `${plural(imageCount, "image", "images")} from ${plural(holders, "institution", "institutions")}`
      : plural(imageCount, "image", "images"),
    literature:
      literatureCount === null
        ? "Searching CrossRef"
        : `${plural(literatureCount, "publication", "publications")} on ${name}`,
  };

  const tabId = (id: TabId) => `${baseId}-tab-${id}`;
  const panelId = (id: TabId) => `${baseId}-panel-${id}`;

  return (
    <section aria-label={`${name} classification, specimens and literature`}>
      <div
        role="tablist"
        aria-label={`${name} sections`}
        onKeyDown={onKeyDown}
        className="flex items-end gap-1 overflow-x-auto [scrollbar-width:none]"
      >
        {TAB_IDS.map((id) => {
          const selected = active === id;
          const badge = badges[id];

          return (
            <button
              key={id}
              ref={(node) => {
                tabRefs.current[id] = node;
              }}
              id={tabId(id)}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={panelId(id)}
              tabIndex={selected ? 0 : -1}
              onClick={() => select(id)}
              className={`flex items-center gap-2 whitespace-nowrap rounded-t-xl border border-b-0 px-3 text-sm transition-colors sm:px-4 sm:text-base focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-pacific-blue-500 ${
                selected
                  ? `${SURFACE} relative z-10 -mb-px pb-2.5 pt-3 font-semibold text-deep-mocha-900 dark:text-white`
                  : "border-deep-mocha-200/80 bg-deep-mocha-100/70 py-2 text-deep-mocha-600 hover:bg-deep-mocha-100 hover:text-deep-mocha-900 dark:border-deep-mocha-700/80 dark:bg-transparent dark:text-deep-mocha-400 dark:hover:bg-deep-mocha-800/50 dark:hover:text-white"
              }`}
            >
              {TAB_LABELS[id]}
              {/* Not on a phone, where three labels fill the row and the
                  line inside the card gives the same count. */}
              {badge !== null ? (
                <span className="hidden text-xs font-normal tabular-nums text-deep-mocha-500 sm:inline dark:text-deep-mocha-400">
                  {formatCount(badge)}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      <div className={`rounded-xl rounded-tl-none border ${SURFACE}`}>
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 pt-4 sm:px-6">
          <p
            aria-live="polite"
            className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400"
          >
            {summaries[active]}
          </p>
          {/* Hidden rather than unmounted, so the filter keeps its text while
              the tree it filters keeps its filtered state. */}
          {controls ? (
            <div className={active === "classification" ? "" : "hidden"}>
              {controls}
            </div>
          ) : null}
        </div>

        <div
          id={panelId("classification")}
          role="tabpanel"
          aria-labelledby={tabId("classification")}
          hidden={active !== "classification"}
          className="p-4 sm:px-6"
        >
          {children}
        </div>

        <div
          id={panelId("specimens")}
          role="tabpanel"
          aria-labelledby={tabId("specimens")}
          hidden={active !== "specimens"}
          className="p-4 sm:px-6 sm:pb-6"
        >
          {institutions.length > 0 ? (
            <InstitutionDonut institutions={institutions} />
          ) : (
            <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
              Holding institutions are not available for these images.
            </p>
          )}
        </div>

        <div
          id={panelId("literature")}
          role="tabpanel"
          aria-labelledby={tabId("literature")}
          hidden={active !== "literature"}
          className="p-4 sm:px-6"
        >
          {literatureOpened ? (
            <HigherTaxonLiterature
              rank={rank}
              name={name}
              context={context}
              onCount={setLiteratureCount}
            />
          ) : null}
        </div>
      </div>
    </section>
  );
}
