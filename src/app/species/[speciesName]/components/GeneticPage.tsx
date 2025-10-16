interface GeneticPageProps {
  speciesName: string;
}

export function GeneticPage({ speciesName }: GeneticPageProps) {
  return (
    <div>
      <h2 className="text-2xl font-semibold mb-4">
        Genetic Information for {speciesName}
      </h2>
      <p className="text-gray-700">
        This section will provide genetic data, including genome sequences,
        genetic markers, and related research articles.
      </p>
    </div>
  );
}
