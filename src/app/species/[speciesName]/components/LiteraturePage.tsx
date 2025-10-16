interface LiteraturePageProps {
  speciesName: string;
}

export function LiteraturePage({ speciesName }: LiteraturePageProps) {
  return (
    <div>
      <h2 className="text-2xl font-semibold mb-4">
        Literature for {speciesName}
      </h2>
      <p className="text-gray-700">
        This section will provide a list of scientific papers, articles, and
        books related to the species.
      </p>
    </div>
  );
}
