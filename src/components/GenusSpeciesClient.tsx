'use client'; // Mark this component as a Client Component

import React, { useState, useEffect } from 'react';
import Image from "next/image";
import Link from "next/link";

// Import the SpeciesData type
import { SpeciesData } from '@/lib/speciesData';

// Define the props type expected by this component
interface GenusSpeciesClientProps {
  initialSpeciesList: SpeciesData[];
}

// Define the Client Component that handles state and rendering for Species within a Genus
export default function GenusSpeciesClient({ initialSpeciesList }: GenusSpeciesClientProps) {
  const [searchTerm, setSearchTerm] = useState('');
  // State for filtered species
  const [filteredSpecies, setFilteredSpecies] = useState<SpeciesData[]>(initialSpeciesList);

  // Effect to filter species when search term changes (by scientific or common name)
  useEffect(() => {
    const lowerCaseSearchTerm = searchTerm.toLowerCase();
    if (lowerCaseSearchTerm === '') {
      setFilteredSpecies(initialSpeciesList);
    } else {
      setFilteredSpecies(
        initialSpeciesList.filter(species => 
          species.name.toLowerCase().includes(lowerCaseSearchTerm) ||
          species.commonName.toLowerCase().includes(lowerCaseSearchTerm)
        )
      );
    }
  }, [searchTerm, initialSpeciesList]);

  return (
    <section>
      {/* Search Input specific to this species list */}
      <div className="mb-6">
        <input 
          type="text"
          placeholder="Filter species by name..." // Keep placeholder relevant
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full md:w-1/2 px-4 py-2 rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-green-500"
        />
      </div>

      {/* Render the filtered list of species */} 
      {filteredSpecies.length === 0 ? (
         <p className="text-gray-500">
          {searchTerm ? 'No species found matching your filter.' : 'No species found in this genus.'}
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {/* Map over filteredSpecies */} 
          {filteredSpecies.map((species, index) => (
            // Link to the individual species page (e.g., /species/Danaus_plexippus)
            <Link key={index} href={`/species/${species.originalFolderName}`} legacyBehavior={false}>
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
                  {/* Revert color classes on scientific name */}
                  <h2 
                    className="text-base font-semibold truncate italic text-center"
                    title={species.name}
                  >
                    {species.name}
                  </h2>
                  {/* Revert color classes on common name */}
                  <p 
                    className="text-sm text-gray-600 dark:text-gray-400 truncate text-center"
                    title={species.commonName}
                  >
                    {species.commonName}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
} 