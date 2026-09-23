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

/**
 * @param align "start" sets the tabs and the panel flush left, for a search
 *   that sits in a column beside other content rather than centred on the
 *   page on its own.
 */
const SearchSwitcher = ({
  align = "center",
  className = "my-8",
}: {
  align?: "center" | "start";
  className?: string;
}) => {
  const [mode, setMode] = useState(tabData[1].id);
  const baseBtn =
    "px-4 py-1.5 rounded-full text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-hunter-green-500 focus:ring-offset-2 dark:focus:ring-offset-deep-mocha-900";
  
  // One selected look for every mode, matching the one panel they share
  // below. The modes used to wear three different fills — two gradients and
  // a green — so the tab strip changed colour as well as selection.
  const active =
    "bg-hunter-green-200 dark:bg-hunter-green-900 text-deep-mocha-900 dark:text-hunter-green-50 shadow";

  const inactive =
    "text-deep-mocha-700 dark:text-deep-mocha-300 hover:bg-deep-mocha-200/70 dark:hover:bg-deep-mocha-700/70";

  return (
    <div
      className={`flex flex-col w-full ${align === "start" ? "items-start" : "items-center"} ${className}`}
    >
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
              className={`${baseBtn} ${mode === tab.id ? active : inactive}`}
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
