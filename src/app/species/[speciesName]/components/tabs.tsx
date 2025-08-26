"use client";

import React, { useState } from "react";
import { SpeciesOverview } from "./overview";
import { TaxonomyData } from "@/lib/speciesData";
import { Occurrence } from "@/lib/types";
import SpeciesTraits from "./traits";

// Define the props for the TabsComponent
interface TabsComponentProps {
  speciesName: string;
  taxonomyData: TaxonomyData | null;
  gbifOccurrences: Occurrence[];
}

const TabsComponent: React.FC<TabsComponentProps> = ({
  speciesName,
  taxonomyData,
  gbifOccurrences,
}) => {
  // Tab data with placeholders for Traits and Specimens
  const tabsData = [
    {
      id: "overview",
      label: "Overview",
      content: (
        <SpeciesOverview
          speciesName={speciesName}
          taxonomyData={taxonomyData}
          gbifOccurrences={gbifOccurrences}
        />
      ),
    },
    {
      id: "traits",
      label: "Traits",
      content: (
        <SpeciesTraits
          description={taxonomyData?.description || "No description available."}
        />
      ),
    },
    {
      id: "specimens",
      label: "Specimens",
      content: (
        <div className="space-y-4">
          <p className="text-gray-700">
            This section will list museum specimens, including collection data
            and images.
          </p>
        </div>
      ),
    },
    {
      id: "Wikipedia",
      label: "Wikipedia",
      content: (
        <div className="space-y-4">
          <p className="text-gray-700">
            This section will display images related to the species.
          </p>
        </div>
      ),
    },
  ];

  const [activeTab, setActiveTab] = useState(tabsData[0].id);

  const baseBtn =
    "px-4 py-1.5 rounded-full text-sm font-medium transition-colors";
  const active =
    "bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-white shadow";
  const inactive =
    "text-gray-600 dark:text-gray-300 hover:bg-gray-200/70 dark:hover:bg-gray-700/70";

  return (
    <div className="flex flex-col items-center w-full">
      <div className="flex items-center gap-3 mt-2">
        <div
          className="flex rounded-full border border-gray-300 dark:border-gray-600 bg-white/70 dark:bg-gray-800/70 backdrop-blur"
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

      <div className="p-4 mt-2 rounded-lg w-full">
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
