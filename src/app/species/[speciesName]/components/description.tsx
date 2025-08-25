export function SpeciesDescription({
  description,
  species,
}: {
  description: string | null;
  species: string;
}) {
  return (
    <div>
      <h2 className="text-2xl font-semibold mt-4">Description</h2>
      <SpeciesDescriptionText description={description} species={species} />
    </div>
  );
}

function SpeciesDescriptionText({
  description,
  species,
}: {
  description: string | null;
  species: string;
}) {
  if (!description || description.trim() === "") {
    return (
      <p className="text-gray-500 dark:text-gray-400 mt-2">
        No description available for <i>{species}</i>.
      </p>
    );
  }
  return (
    <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
      {description}
    </p>
  );
}
