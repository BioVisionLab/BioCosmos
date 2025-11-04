"use client";

import React, { useState } from "react";

export default function SemanticSearchBar({
  mode,
  icon: Icon,
  onSubmit,
  placeholder = "Describe species traits, e.g., 'butterfly with orange wings and black lines'",
}: {
  mode: string;
  icon: React.ComponentType;
  onSubmit: (query: string, mode: string) => void;
  placeholder?: string;
}) {
  const [searchTerm, setSearchTerm] = useState("");

  const handleSearchSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = searchTerm.trim();
    if (!query) return;

    onSubmit(query, mode);
  };

  return (
    <form
      onSubmit={handleSearchSubmit}
      className="flex flex-col gap-2"
      aria-label="Species search form"
    >
      {/* Input + Actions */}
      <div className="flex items-center gap-2 w-full h-12">
        <div
          className={`
        relative flex items-stretch gap-2 rounded-l-2xl px-4 py-2
        bg-white/70 dark:bg-gray-800/60 backdrop-blur
        ring-1 ring-gray-200 dark:ring-gray-700
        shadow-sm hover:shadow-md transition-all
        focus-within:ring-2 focus-within:ring-green-500/60
        w-full h-full
        `}
        >
          <div className="flex items-center">
            <Icon />
          </div>
          {/* Text Input */}
          <input
            type="text"
            aria-label={"Semantic species search input"}
            placeholder={placeholder}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className={`
          flex-1 bg-transparent border-0 focus:outline-none
          placeholder:text-gray-400 dark:placeholder:text-gray-500
          text-gray-800 dark:text-gray-100
          text-sm md:text-base
          disabled:opacity-60
        `}
          />
        </div>
        <div className="col-span-2 flex items-center h-full">
          <button
            type="submit"
            disabled={!searchTerm.trim()}
            className={`
              flex items-center justify-center 
              px-5 text-sm font-medium rounded-r-2xl
              bg-green-600 text-white hover:bg-green-700
              ring-1 ring-emerald-200 dark:ring-emerald-600
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors h-full backdrop-blur
              `}
            aria-label="Submit species search"
          >
            Search
          </button>
        </div>
      </div>
    </form>
  );
}
