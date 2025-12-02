import { useState } from "react";

export default function SemanticForm({
  mode,
  icon: Icon,
  onSubmit,
  query,
  placeholder = "Describe species traits, e.g., 'butterfly with orange wings and black lines'",
}: {
  mode: string;
  icon: React.ComponentType<{ className?: string }>;
  onSubmit: (query: string, mode: string) => void;
  query?: string;
  placeholder?: string;
}) {
  const [searchTerm, setSearchTerm] = useState(query || "");
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
        focus-within:ring-2 focus-within:ring-emerald-500/60
        w-full h-full
        `}
        >
          <div className="flex items-center">
            <Icon
              className={`h-6 w-6 transition-colors ${
                searchTerm
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-gray-400 dark:text-gray-500"
              }`}
            />
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
              flex items-center justify-center px-5 text-sm font-medium rounded-r-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white hover:shadow-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 disabled:from-gray-300 disabled:to-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed dark:disabled:from-gray-600 dark:disabled:to-gray-600 dark:disabled:text-gray-400 h-full 
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
