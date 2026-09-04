"use client";

import React, { useCallback, useState } from "react";
import dynamic from "next/dynamic";
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

  const baseBtn =
    "px-4 py-1.5 rounded-full text-sm font-medium transition-colors";
  const active =
    "bg-gradient-to-r from-hunter-green-500 via-pacific-blue-500 to-frozen-water-500 text-white shadow";
  const inactive =
    "text-deep-mocha-600 dark:text-deep-mocha-300 hover:bg-deep-mocha-200/70 dark:hover:bg-deep-mocha-700/70";

  return (
    <div className="flex flex-col items-center w-full">
      <div className="w-full overflow-x-auto mt-2 flex md:justify-center md:px-0 scrollbar-hide">
        <div
          className="inline-flex shrink-0 rounded-full border border-deep-mocha-300 dark:border-deep-mocha-600 bg-white/70 dark:bg-deep-mocha-800/70 backdrop-blur-lg whitespace-nowrap"
          role="tablist"
        >
          {TAB_IDS.map((id) => (
            <button
              id={`tab-${id}`}
              key={id}
              type="button"
              onClick={() => selectTab(id)}
              className={`${baseBtn} ${activeTab === id ? active : inactive}`}
              role="tab"
              aria-selected={activeTab === id}
              aria-controls={`tabpanel-${id}`}
              tabIndex={activeTab === id ? 0 : -1}
            >
              {TAB_LABELS[id]}
            </button>
          ))}
        </div>
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

export default TabsComponent;
