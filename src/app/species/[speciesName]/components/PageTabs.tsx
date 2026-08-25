"use client";

import React, { useState } from "react";
import { SpeciesOverview } from "./SpeciesOverview";
import { SpeciesData } from "@/lib/speciesData";
import WikipediaPage from "./WikipediaPage";
import { LiteraturePage } from "./LiteraturePage";
import BiologyPage from "./BiologyPage";
import SpecimensTab from "./SpecimensTab";

// Define the props for the TabsComponent
interface TabsComponentProps {
  speciesData: SpeciesData;
  // route slug (folder name) like 'zeuxidia_amethystus'
  speciesSlug?: string;
}

const TabsComponent: React.FC<TabsComponentProps> = ({
  speciesData,
  speciesSlug,
}) => {
  // Tab data with placeholders for Traits and Specimens
  const tabsData = [
    {
      id: "overview",
      label: "Overview",
      content: (
        <SpeciesOverview
          taxonomy={speciesData.taxonomy}
          traits={speciesData.traits}
        />
      ),
    },
    {
      id: "biology",
      label: "Biology",
      content: (
        <BiologyPage
          speciesName={speciesData.taxonomy?.species ?? ""}
          traits={speciesData.traits}
        />
      ),
    },

    {
      // Using new SpecimensTab implementation (instead of SpecimenPage)
      id: "specimens",
      label: "Specimens",
      content: (
        <SpecimensTab
          // prefer the route slug when available so gallery links use correct folder name
          speciesName={speciesSlug ?? speciesData.taxonomy?.species ?? ""}
        />
      ),
    },
    {
      id: "wikipedia",
      label: "Wikipedia",
      content: (
        <WikipediaPage speciesName={speciesData.taxonomy?.species ?? ""} />
      ),
    },
    {
      id: "literature",
      label: "Literature",
      content: (
        <LiteraturePage speciesName={speciesData.taxonomy?.species ?? ""} />
      ),
    },
  ];

  const [activeTab, setActiveTab] = useState(tabsData[0].id);

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
          {tabsData.map((tab) => (
            <button
              id={`tab-${tab.id}`}
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`${baseBtn} ${
                activeTab === tab.id ? active : inactive
              }`}
              role="tab"
              aria-controls={`tabpanel-${tab.id}`}
              tabIndex={activeTab === tab.id ? 0 : -1}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8 rounded-xl w-full">
        {tabsData.map((tab) => (
          <div
            key={tab.id}
            id={`tabpanel-${tab.id}`}
            role="tabpanel"
            aria-labelledby={`tab-${tab.id}`}
            className={activeTab === tab.id ? "" : "hidden"}
          >
            {tab.content}
          </div>
        ))}
      </div>
    </div>
  );
};

export default TabsComponent;
