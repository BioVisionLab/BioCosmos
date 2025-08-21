'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
// Remove direct import of getSpeciesData
// import { getSpeciesData, SpeciesData } from '@/lib/speciesData'; 
// Need SpeciesData type for state/props
import type { SpeciesData } from '@/lib/speciesData'; 
import Link from 'next/link';
import Image from 'next/image';

// Define the type for the semantic result object from the Python service
interface SemanticResultItem {
    species_folder: string;
    best_image_filename: string;
}

// Reusable component for displaying a species card (similar to GenusSpeciesClient)
const SpeciesCard: React.FC<{ species: SpeciesData }> = ({ species }) => (
  <Link href={`/species/${species.originalFolderName}`} legacyBehavior={false}>
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden flex flex-col group cursor-pointer h-full">
      <div className="relative w-full aspect-square overflow-hidden bg-gray-100 dark:bg-gray-700">
        {species.imageUrl ? (
          <Image
            src={species.imageUrl}
            alt={species.name}
            fill
            sizes="(max-width: 640px) 50vw, (max-width: 768px) 33vw, (max-width: 1024px) 25vw, (max-width: 1280px) 20vw, 16.6vw"
            style={{ objectFit: "contain" }}
            className="transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <span className="text-gray-400 text-sm">No image</span>
          </div>
        )}
      </div>
      <div className="p-3 flex-grow flex flex-col justify-center">
        <h2 
          className="text-base font-semibold truncate italic text-center"
          title={species.name}
        >
          {species.name}
        </h2>
        <p 
          className="text-sm text-gray-600 dark:text-gray-400 truncate text-center"
          title={species.commonName}
        >
          {species.commonName}
        </p>
      </div>
    </div>
  </Link>
);

function SearchResults() {
  const searchParams = useSearchParams();
  const query = searchParams.get('q'); // For text search
  // No longer using idsParam directly for fetching, handled by API routes
  const mode = searchParams.get('mode') || (searchParams.get('ids') ? 'semantic' : 'text'); // Determine mode based on presence of ids or query

  const [results, setResults] = useState<SpeciesData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    setResults([]);

    const fetchResults = async () => {
      try {
        let data: SpeciesData[] = [];
        if (mode === 'semantic') {
            // Semantic search: HeaderClient already called /api/semantic-search
            // and put results (list of objects) into the 'ids' parameter (encoded).
            // Now, we fetch the details using those results.
            const semanticResultsParam = searchParams.get('ids'); // Re-read param, though mode check is enough
            if (!semanticResultsParam) {
                console.log('Semantic mode but no results (ids param) found in URL.');
                return; // Or throw error?
            }
            
            // Decode and parse the results (list of objects) passed from HeaderClient
            // Note: This assumes the python service is returning JSON stringified list of objects
            // If python service returns JSON array, the /api/semantic-search needs to forward that
            // And HeaderClient needs to encode that array. Let's assume API route handles it.
            const semanticResultItems: SemanticResultItem[] = JSON.parse(decodeURIComponent(semanticResultsParam));

            console.log('Decoded semantic result items:', semanticResultItems);

            if (semanticResultItems.length === 0) {
                 console.log('No semantic results to display.');
                 return;
            }

            // Extract just the species folders to fetch details
            const speciesFolders = semanticResultItems.map(item => item.species_folder);

            // Fetch results from the details API route
            const response = await fetch(`/api/species-details?ids=${encodeURIComponent(speciesFolders.join(','))}`);
            if (!response.ok) {
                throw new Error('Semantic search details request failed');
            }
            const speciesDetailsList: SpeciesData[] = await response.json();

            // Map the fetched details and override the imageUrl
            const resultMap = new Map(speciesDetailsList.map(s => [s.originalFolderName, s]));
            data = semanticResultItems.map(item => {
                const speciesData = resultMap.get(item.species_folder);
                if (speciesData) {
                    // IMPORTANT: Override the imageUrl with the best matching one
                    const updatedData = {
                         ...speciesData, 
                         imageUrl: `/images/nymphalidae_new/${item.species_folder}/${item.best_image_filename}`
                    };
                     // console.log(`Overriding image for ${item.species_folder} to ${updatedData.imageUrl}`);
                     return updatedData;
                }
                return null; // Should not happen if API returned correctly
            }).filter((species): species is SpeciesData => species !== null);
            
            console.log('Processed semantic results with overridden images:', data);

        } else if (mode === 'text' && query) {
          // Fetch results from text search API
          console.log('Fetching results for text search query:', query);
          const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
          if (!response.ok) {
            throw new Error('Text search request failed');
          }
          data = await response.json();
          console.log('Fetched text results:', data);
        
        } else {
           // No query or IDs provided
           console.log('No search query or IDs provided.');
        }
        setResults(data);

      } catch (err) {
        console.error("Search fetch error:", err);
        setError(err instanceof Error ? err.message : 'Failed to fetch search results. Please try again.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchResults();

  }, [query, mode, searchParams]); // Depend on searchParams to re-run when URL changes

  // Determine title based on mode
  const getTitle = () => {
      if (mode === 'semantic') return "Semantic Search Results";
      if (query) return `Text Search Results for "${query}"`;
      return "Search Results";
  };

  return (
    <section>
      <h1 className="text-3xl font-bold mb-6">
        {getTitle()}
      </h1>

      {isLoading && <p>Loading results...</p>}
      {error && <p className="text-red-500">{error}</p>}

      {!isLoading && !error && results.length === 0 && (mode === 'text' && query) && (
        <p>No species found matching text query `{query}`.</p>
      )}
       {!isLoading && !error && results.length === 0 && (mode === 'semantic') && (
        <p>No species found for the provided semantic search results.</p>
      )}
      {!isLoading && !error && results.length === 0 && !(query || searchParams.get('ids')) && (
        <p>Please enter a search term in the header bar.</p>
      )}

      {!isLoading && !error && results.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {results.map(species => (
            <SpeciesCard key={species.originalFolderName} species={species} />
          ))}
        </div>
      )}
    </section>
  );
}

// Wrap the client component in Suspense for useSearchParams
export default function SearchPage() {
  return (
    <Suspense fallback={<div>Loading search...</div>}> 
      <SearchResults />
    </Suspense>
  );
} 