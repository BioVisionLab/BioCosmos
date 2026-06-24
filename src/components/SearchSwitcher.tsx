"use client";

import React, { useState } from "react";
import ImageSearch from "./ImageSearch";
import SemanticSearchBar from "./SemanticTextSearch";
import TextSearch from "./TextSearch";

const tabData = [
  {
    id: "semantic",
    label: "Semantic Search",
    content: <SemanticSearchBar />,
  },
  { id: "text", label: "Text Search", content: <TextSearch /> },
  { id: "image", label: "Image Search", content: <ImageSearch /> },
];

const SearchSwitcher = () => {
  const [mode, setMode] = useState(tabData[1].id);
  const baseBtn =
    "px-4 py-1.5 rounded-full text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-hunter-green-500 focus:ring-offset-2 dark:focus:ring-offset-deep-mocha-900";
  
  const getActiveClass = (id: string) => {
    switch (id) {
      case "semantic":
        return "bg-gradient-to-r from-hunter-green-600 via-pacific-blue-600 to-frozen-water-700 text-white shadow";
      case "text":
        return "bg-hunter-green-200 dark:bg-hunter-green-900 text-deep-mocha-900 dark:text-hunter-green-50 shadow";
      case "image":
        return "bg-gradient-to-r from-hunter-green-600 to-pacific-blue-700 text-white shadow";
      default:
        return "bg-hunter-green-600 text-white shadow";
    }
  };

  const inactive =
    "text-deep-mocha-700 dark:text-deep-mocha-300 hover:bg-deep-mocha-200/70 dark:hover:bg-deep-mocha-700/70";

  return (
    <div className="flex flex-col items-center w-full my-8">
      <div className="flex items-center gap-3 mt-2">
        <div 
          className="flex rounded-full border border-deep-mocha-300 dark:border-deep-mocha-600 bg-white/70 dark:bg-deep-mocha-800/70 backdrop-blur"
          role="tablist"
          aria-label="Search Modes"
        >
          {tabData.map((tab) => (
            <button
              id={`tab-${tab.id}`}
              key={tab.id}
              role="tab"
              type="button"
              onClick={() => setMode(tab.id)}
              className={`${baseBtn} ${mode === tab.id ? getActiveClass(tab.id) : inactive}`}
              aria-controls={`tabpanel-${tab.id}`}
              aria-selected={mode === tab.id}
              tabIndex={mode === tab.id ? 0 : -1}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-5 w-full max-w-2xl">
        {tabData.map((tab) => (
          <div
            key={tab.id}
            id={`tabpanel-${tab.id}`}
            role="tabpanel"
            aria-labelledby={`tab-${tab.id}`}
            className={mode === tab.id ? "" : "hidden"}
          >
            {tab.content}
          </div>
        ))}
      </div>
    </div>
  );
};

export default SearchSwitcher;
