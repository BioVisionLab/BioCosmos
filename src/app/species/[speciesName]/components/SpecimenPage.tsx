interface SpecimenPageProps {
  speciesName: string;
}

export function SpecimenPage({ speciesName }: SpecimenPageProps) {
  return (
    <div>
      <h2 className="text-2xl font-semibold mb-4">
        Specimens of {speciesName}
      </h2>
      <p className="text-gray-700">
        This section will list museum specimens, including collection data and
        images.
      </p>
    </div>
  );
}
