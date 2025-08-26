"use client";

import React, { useState } from "react";
import SearchBar from "./TextSearch";
import ImageSearch from "./ImageSearch";

const SearchSwitcher = () => {
  const [mode, setMode] = useState<"text" | "image">("text");
  const baseBtn =
    "px-4 py-1.5 rounded-full text-sm font-medium transition-colors";
  const active =
    "bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-white shadow";
  const inactive =
    "text-gray-600 dark:text-gray-300 hover:bg-gray-200/70 dark:hover:bg-gray-700/70";

  return (
    <div className="flex flex-col items-center w-full">
      <div className="flex items-center gap-3 mt-2">
        <div className="flex rounded-full border border-gray-300 dark:border-gray-600 bg-white/70 dark:bg-gray-800/70 backdrop-blur">
          <button
            type="button"
            onClick={() => setMode("text")}
            className={`${baseBtn} ${
              mode === "text" ? active : inactive
            }`}
          >
            Text Search
          </button>
          <button
            type="button"
            onClick={() => setMode("image")}
            className={`${baseBtn} ${
              mode === "image" ? active : inactive
            }`}
          >
            Image Search
          </button>
        </div>
      </div>
      <div className="mt-5 w-full max-w-xl">
        {mode === "text" ? (
          <div className="animate-fade-in">
            <SearchBar />
          </div>
        ) : (
          <div className="animate-fade-in">
            <ImageSearch />
          </div>
        )}
      </div>
      <style jsx global>{`
        .animate-fade-in {
          animation: fadeIn 220ms ease-out;
        }
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(4px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
};

export default SearchSwitcher;
