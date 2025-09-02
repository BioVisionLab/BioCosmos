import { LepTraits } from "@/lib/speciesData";

function SpeciesTraits({ traits }: { traits: LepTraits | null }) {
  if (!traits) {
    return <p className="text-gray-200">No traits available.</p>;
  }

  return (
    <div>
      <ul className="list-disc list-inside">
        {Object.entries(traits)
          .filter(([, value]) => value != null && value !== "")
          .map(([key, value]) => (
            <li key={key} className="text-gray-200">
              <span className="font-medium">{key.replace(/_/g, " ")}:</span>{" "}
              {value}
            </li>
          ))}
      </ul>
    </div>
  );
}

export default SpeciesTraits;
