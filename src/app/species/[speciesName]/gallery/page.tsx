export default function SpeciesImageGallery({
  speciesName,
}: {
  speciesName: string;
}) {
  // Display simple placeholder for now
  return (
    <div className="w-full aspect-video flex items-center justify-center border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-100 dark:bg-gray-900">
      <p className="text-gray-500 dark:text-gray-400">
        Image Gallery Placeholder
      </p>
    </div>
  );
}
