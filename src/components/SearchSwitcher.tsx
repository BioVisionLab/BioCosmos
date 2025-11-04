"use client";

import React, { useState } from "react";
import ImageSearch from "./ImageSearch";
import SemanticSearchBar from "./SemanticTextSearch";
import TextSearch from "./TextSearch";

const tabData = [
  { id: "text", label: "Text Search", content: <TextSearch /> },
  {
    id: "semantic",
    label: "Semantic Search",
    content: <SemanticSearchBar />,
  },
  { id: "image", label: "Image Search", content: <ImageSearch /> },
];

const SearchSwitcher = () => {
  const [mode, setMode] = useState(tabData[1].id);
  const baseBtn =
    "px-4 py-1.5 rounded-full text-sm font-medium transition-colors";
  const active =
    "bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-white shadow";
  const inactive =
    "text-gray-600 dark:text-gray-300 hover:bg-gray-200/70 dark:hover:bg-gray-700/70";

  return (
    <div className="flex flex-col items-center w-full my-8">
      <div className="flex items-center gap-3 mt-2">
        <div className="flex rounded-full border border-gray-300 dark:border-gray-600 bg-white/70 dark:bg-gray-800/70 backdrop-blur">
          {tabData.map((tab) => (
            <button
              id={`tab-${tab.id}`}
              key={tab.id}
              type="button"
              onClick={() => setMode(tab.id)}
              className={`${baseBtn} ${mode === tab.id ? active : inactive}`}
              aria-controls={`tabpanel-${tab.id}`}
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
