import { LepTraits } from "@/lib/speciesData";

function SpeciesTraits({ traits }: { traits: LepTraits | null }) {
  if (!traits) {
    return <p className="text-gray-200">No traits available.</p>;
  }

  return (
    <div>
      <h3 className="text-lg font-semibold">Traits</h3>
      <ul className="list-disc list-inside">
        {Object.entries(traits).map(([key, value]) => (
          <li key={key} className="text-gray-700">
            <span className="font-medium">{key.replace(/_/g, " ")}:</span>{" "}
            {value}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default SpeciesTraits;
