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
            This section will list museum and herbarium specimens, including
            collection data and images.
          </p>
        </div>
      ),
    },
  ];

  const [activeTab, setActiveTab] = useState(tabsData[0].id);

  return (
    <div className="mx-auto">
      <div className="flex" role="tablist" aria-label="Tabs">
        {tabsData.map((tab) => (
          <button
            id={`tab-${tab.id}`}
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`py-2 px-4 text-sm font-medium transition-colors duration-300 focus:outline-none ${
              activeTab === tab.id
                ? "border-b-2 border-blue-500 text-blue-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
            role="tab"
            tabIndex={activeTab === tab.id ? 0 : -1}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="p-4 mt-2 rounded-lg shadow-md">
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
