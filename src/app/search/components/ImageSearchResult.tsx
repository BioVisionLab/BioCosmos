export function ImageSearchResult({ imageUrl }: { imageUrl: string }) {
  return (
    <div className="items-center max-w-7xl w-full px-4 mx-auto">
      <div className="mb-4">
        <a href="/" className="text-blue-600 hover:underline">
          &larr; Back to Home
        </a>
      </div>
      <div className="mt-2 mb-6 text-center">
        <h1 className="text-xl sm:text-4xl font-extrabold tracking-tight font-serif bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-transparent bg-clip-text drop-shadow">
          Search Results
        </h1>
      </div>
      <div className="mt-5">
        <div className="flex flex-col items-center mt-24">
          <div className="relative w-full max-w-3xl aspect-square border border-gray-300 dark:border-gray-700 rounded-lg overflow-hidden bg-gray-100 dark:bg-gray-900">
            <img
              src={imageUrl}
              alt="Search Result"
              className="w-full h-full object-contain"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
