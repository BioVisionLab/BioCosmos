function SimilarSpecies({ species }: { species: string }) {
  return (
    <div className="mt-4">
      <h2 className="text-2xl font-semibold">Similar Species</h2>
      <p className="text-gray-500 dark:text-gray-400">
        Top 10 species visually similar to <i>{species}</i> based on coloration.
      </p>
    </div>
  );
}

export default SimilarSpecies;
