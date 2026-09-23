"use client";

import React, {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import dynamic from "next/dynamic";
import { Menu } from "lucide-react";
import { SpeciesOverview } from "./SpeciesOverview";
import { SpeciesData } from "@/lib/speciesData";
import { ImageLoading } from "@/components/Loadings";

// Every tab except the default one is code-split and only mounted once the
// user actually opens it. Previously all five panels were constructed on
// mount and merely hidden with CSS, so a single page load fired the
// Wikipedia, CrossRef, GenBank, UMAP and specimen requests at once.
const tabLoading = (msg: string) => {
  const Loading = () => (
    <div className="flex items-center justify-center py-16">
      <ImageLoading size={180} msg={msg} />
    </div>
  );
  Loading.displayName = `TabLoading(${msg})`;
  return Loading;
};

const BiologyPage = dynamic(() => import("./BiologyPage"), {
  ssr: false,
  loading: tabLoading("Loading biology"),
});

const SpecimensTab = dynamic(() => import("./SpecimensTab"), {
  ssr: false,
  loading: tabLoading("Loading specimens"),
});

const WikipediaPage = dynamic(() => import("./WikipediaPage"), {
  ssr: false,
  loading: tabLoading("Loading Wikipedia article"),
});

const LiteraturePage = dynamic(
  () => import("./LiteraturePage").then((m) => m.LiteraturePage),
  {
    ssr: false,
    loading: tabLoading("Loading literature"),
  },
);

// Define the props for the TabsComponent
interface TabsComponentProps {
  speciesData: SpeciesData | null;
  // route slug (folder name) like 'zeuxidia_amethystus'
  speciesSlug?: string;
}

const TAB_IDS = [
  "overview",
  "biology",
  "specimens",
  "wikipedia",
  "literature",
] as const;

type TabId = (typeof TAB_IDS)[number];

// Five pills do not fit a phone, and the row used to scroll sideways to reach
// the last two. When the full row does not fit, the three a reader actually
// comes for stay in the bar and the external-source tabs move behind a menu
// button. Wherever all five fit, they are all shown and there is no menu.
const PRIMARY_TABS: readonly TabId[] = ["overview", "biology", "specimens"];
const MORE_TABS: readonly TabId[] = ["wikipedia", "literature"];

const TAB_LABELS: Record<TabId, string> = {
  overview: "Overview",
  biology: "Biology",
  specimens: "Specimens",
  wikipedia: "Wikipedia",
  literature: "Literature",
};

const TabsComponent: React.FC<TabsComponentProps> = ({
  speciesData,
  speciesSlug,
}) => {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  // Tabs the user has opened at least once. Visited panels stay mounted (but
  // hidden) so switching back and forth doesn't refetch their data.
  const [visitedTabs, setVisitedTabs] = useState<Set<TabId>>(
    () => new Set<TabId>(["overview"]),
  );

  const selectTab = useCallback((id: TabId) => {
    setActiveTab(id);
    setVisitedTabs((prev) => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  }, []);

  const speciesName = speciesData?.taxonomy?.species ?? "";

  const renderTab = (id: TabId) => {
    switch (id) {
      case "overview":
        return (
          <SpeciesOverview
            taxonomy={speciesData?.taxonomy ?? null}
            traits={speciesData?.traits ?? null}
            speciesSlug={speciesSlug ?? speciesName}
            onViewSpecimens={() => selectTab("specimens")}
          />
        );
      case "biology":
        return (
          <BiologyPage
            speciesName={speciesName}
            traits={speciesData?.traits ?? null}
          />
        );
      case "specimens":
        return (
          // prefer the route slug when available so gallery links use correct folder name
          <SpecimensTab speciesName={speciesSlug ?? speciesName} />
        );
      case "wikipedia":
        return <WikipediaPage speciesName={speciesName} />;
      case "literature":
        return <LiteraturePage speciesName={speciesName} />;
    }
  };

  const barClass =
    "inline-flex items-center rounded-full border border-deep-mocha-300 dark:border-deep-mocha-600 bg-white/70 dark:bg-deep-mocha-800/70 backdrop-blur-lg whitespace-nowrap";
  const baseBtn =
    "px-3 sm:px-4 py-1.5 rounded-full text-sm font-medium transition-colors";
  const active =
    "bg-gradient-to-r from-hunter-green-500 via-pacific-blue-500 to-frozen-water-500 text-white shadow";
  const inactive =
    "text-deep-mocha-600 dark:text-deep-mocha-300 hover:bg-deep-mocha-200/70 dark:hover:bg-deep-mocha-700/70";

  const moreActive = MORE_TABS.includes(activeTab);
  const { containerRef, measureRef, mode: layoutMode } = useTabLayout();

  const tabButton = (id: TabId, extraClass = "") => (
    <button
      id={`tab-${id}`}
      key={id}
      type="button"
      onClick={() => selectTab(id)}
      className={`${baseBtn} ${extraClass} ${activeTab === id ? active : inactive}`}
      role="tab"
      aria-selected={activeTab === id}
      aria-controls={`tabpanel-${id}`}
      tabIndex={activeTab === id ? 0 : -1}
    >
      {TAB_LABELS[id]}
    </button>
  );

  // Before the bar has been measured (server render, and the frames before
  // hydration) the `sm` breakpoint stands in for the measurement, so a phone
  // never flashes an overflowing five-pill row.
  const moreTabClass = layoutMode === "auto" ? "hidden sm:inline-block" : "";
  const menuClass = layoutMode === "auto" ? "sm:hidden" : "";

  return (
    <div ref={containerRef} className="flex flex-col items-center w-full">
      {/* The full row, drawn invisibly at its natural width. Measuring this
          rather than the visible bar is what lets the bar switch back to all
          five tabs when the viewport widens again. `w-max` keeps it from
          shrinking to its container, and the clipping wrapper keeps it from
          widening the page on a phone. */}
      <div aria-hidden="true" className="relative h-0 w-full overflow-hidden">
        <div
          ref={measureRef}
          className={`${barClass} pointer-events-none invisible absolute w-max`}
        >
          {TAB_IDS.map((id) => (
            <span key={id} className={`${baseBtn} ${inactive}`}>
              {TAB_LABELS[id]}
            </span>
          ))}
        </div>
      </div>

      <div className={`${barClass} relative z-10 mt-2 max-w-full`}>
        <div
          className="inline-flex"
          role="tablist"
          aria-label="Species sections"
        >
          {PRIMARY_TABS.map((id) => tabButton(id))}
          {layoutMode !== "collapsed"
            ? MORE_TABS.map((id) => tabButton(id, moreTabClass))
            : null}
        </div>
        {layoutMode !== "expanded" ? (
          <div className={menuClass}>
            <MoreTabsMenu
              activeTab={activeTab}
              onSelect={selectTab}
              // In auto mode the inline tabs already carry these ids.
              ownsTabId={layoutMode === "collapsed"}
              buttonClassName={`${baseBtn} inline-flex items-center gap-1.5 ${
                moreActive ? active : inactive
              }`}
            />
          </div>
        ) : null}
      </div>

      <div className="mt-8 rounded-xl w-full">
        {TAB_IDS.filter((id) => visitedTabs.has(id)).map((id) => (
          <div
            key={id}
            id={`tabpanel-${id}`}
            role="tabpanel"
            aria-labelledby={`tab-${id}`}
            className={activeTab === id ? "" : "hidden"}
          >
            {renderTab(id)}
          </div>
        ))}
      </div>
    </div>
  );
};

type TabLayoutMode = "auto" | "expanded" | "collapsed";

/**
 * Whether the full row of tabs fits the width available to it.
 *
 * "auto" until the first measurement, then "expanded" when all five fit and
 * "collapsed" when they do not. Both the container and the hidden full row are
 * observed: the row changes width when the web font finishes loading, and the
 * container whenever the viewport does.
 */
function useTabLayout() {
  const containerRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<TabLayoutMode>("auto");

  useLayoutEffect(() => {
    const container = containerRef.current;
    const measure = measureRef.current;
    if (!container || !measure) return;

    const update = () => {
      const fits = measure.offsetWidth <= container.clientWidth;
      setMode(fits ? "expanded" : "collapsed");
    };
    update();

    const observer = new ResizeObserver(update);
    observer.observe(container);
    observer.observe(measure);
    return () => observer.disconnect();
  }, []);

  return { containerRef, measureRef, mode };
}

/**
 * The overflow menu for the tabs that do not fit the bar.
 *
 * While one of its tabs is open the button takes the active style (and, from
 * `sm` up, that tab's name), so the bar never shows no selection at all.
 */
function MoreTabsMenu({
  activeTab,
  onSelect,
  ownsTabId,
  buttonClassName,
}: {
  activeTab: TabId;
  onSelect: (id: TabId) => void;
  ownsTabId: boolean;
  buttonClassName: string;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const activeMore = MORE_TABS.includes(activeTab) ? activeTab : null;

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        id={ownsTabId && activeMore ? `tab-${activeMore}` : undefined}
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={buttonClassName}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={
          activeMore
            ? `More sections, ${TAB_LABELS[activeMore]} selected`
            : "More sections"
        }
      >
        <Menu aria-hidden="true" className="h-4 w-4" />
        {/* Icon only on a phone: the three primary tabs already fill the
            bar, and the gradient alone says a tab in here is open. */}
        <span className="hidden sm:inline">
          {activeMore ? TAB_LABELS[activeMore] : "More"}
        </span>
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-full z-20 mt-2 min-w-40 overflow-hidden rounded-xl border border-deep-mocha-300 dark:border-deep-mocha-600 bg-white dark:bg-deep-mocha-800 py-1 shadow-lg"
        >
          {MORE_TABS.map((id) => (
            <button
              key={id}
              type="button"
              role="menuitemradio"
              aria-checked={activeTab === id}
              onClick={() => {
                onSelect(id);
                setOpen(false);
              }}
              className={`block w-full px-4 py-2 text-left text-sm transition-colors ${
                activeTab === id
                  ? "font-semibold text-pacific-blue-700 dark:text-pacific-blue-400"
                  : "text-deep-mocha-700 dark:text-deep-mocha-200 hover:bg-deep-mocha-100 dark:hover:bg-deep-mocha-700"
              }`}
            >
              {TAB_LABELS[id]}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default TabsComponent;
