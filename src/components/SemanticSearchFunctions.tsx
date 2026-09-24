const SEARCH_FUNCTIONS = [
  { name: "search_by_common_name", letters: "CN", label: "Common name", color: "bg-violet-100 text-violet-900 dark:bg-violet-900 dark:text-violet-100" },
  { name: "search_by_image_similarity", letters: "IS", label: "Image similarity", color: "bg-blue-100 text-blue-900 dark:bg-blue-900 dark:text-blue-100" },
  { name: "search_by_color", letters: "CO", label: "Color and appearance", color: "bg-orange-100 text-orange-900 dark:bg-orange-900 dark:text-orange-100" },
  { name: "search_by_location", letters: "LO", label: "Location", color: "bg-teal-100 text-teal-900 dark:bg-teal-900 dark:text-teal-100" },
  { name: "search_by_traits", letters: "TR", label: "Ecological traits", color: "bg-green-100 text-green-900 dark:bg-green-900 dark:text-green-100" },
] as const;

function FunctionBadge({ definition }: { definition: typeof SEARCH_FUNCTIONS[number] }) {
  return (
    <span
      className={`inline-flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${definition.color}`}
      aria-label={definition.label}
      title={definition.label}
    >
      {definition.letters}
    </span>
  );
}

export function SemanticFunctionBadges({ toolNames }: { toolNames: string[] }) {
  return (
    <div className="flex flex-wrap justify-center gap-1.5" aria-label="Matching search functions">
      {SEARCH_FUNCTIONS.filter((definition) => toolNames.includes(definition.name)).map((definition) => (
        <FunctionBadge key={definition.name} definition={definition} />
      ))}
    </div>
  );
}

export function SemanticSearchDescription() {
  return (
    <div className="space-y-3 text-sm text-deep-mocha-700 dark:text-deep-mocha-200">
      <p>
        Search by common name, appearance, location, and habitat, or combine all
        four in one query. You can also find species similar to a named species.
      </p>
    </div>
  );
}

export function SemanticSearchLegend() {
  return (
    <div className="space-y-3 text-center text-sm text-deep-mocha-700 dark:text-deep-mocha-200">
      <p>Circles show which search functions matched each result.</p>
      <ul className="flex flex-wrap justify-center gap-x-4 gap-y-2" aria-label="Search function legend">
        {SEARCH_FUNCTIONS.map((definition) => (
          <li key={definition.name} className="flex items-center gap-2">
            <FunctionBadge definition={definition} />
            <span>{definition.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
