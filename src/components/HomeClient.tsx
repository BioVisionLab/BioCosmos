'use client'; // Mark this component as a Client Component

import React, { useState, useEffect } from 'react';
import Image from "next/image";
import Link from "next/link";

// Import the GenusSummary type
import { GenusSummary } from '@/lib/speciesData';

// Update the props type expected by this component
interface HomeClientProps {
  initialGenusList: GenusSummary[];
}

// Define the Client Component that handles state and rendering for Genera
export default function HomeClient({ initialGenusList }: HomeClientProps) {
  const [searchTerm, setSearchTerm] = useState('');
  // State for filtered genera
  const [filteredGenera, setFilteredGenera] = useState<GenusSummary[]>(initialGenusList);

  // Effect to filter genera when search term changes
  useEffect(() => {
    const lowerCaseSearchTerm = searchTerm.toLowerCase();
    if (lowerCaseSearchTerm === '') {
      setFilteredGenera(initialGenusList);
    } else {
      setFilteredGenera(
        initialGenusList.filter(genus => 
          genus.name.toLowerCase().includes(lowerCaseSearchTerm)
        )
      );
    }
  }, [searchTerm, initialGenusList]);

  return (
    <section>
      {/* Update Search Input placeholder */}
      <div className="mb-6">
        <input 
          type="text"
          placeholder="Filter genera by name..." // Updated placeholder
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full md:w-1/2 px-4 py-2 rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-green-500"
        />
      </div>

      {/* Render the filtered list of genera */}
      {filteredGenera.length === 0 ? (
         <p className="text-gray-500">
          {searchTerm ? 'No genera found matching your filter.' : 'No genera found.'}
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {/* Map over filteredGenera */} 
          {filteredGenera.map((genus, index) => (
            // Link to the genus page (e.g., /genus/Danaus)
            <Link key={index} href={`/genus/${genus.name}`} legacyBehavior={false}> 
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden flex flex-col group cursor-pointer h-full">
                <div className="relative w-full aspect-square overflow-hidden bg-gray-100 dark:bg-gray-700"> {/* Added background for missing images */}
                  {genus.representativeImageUrl ? (
                    <Image
                        src={genus.representativeImageUrl} // Use representative image
                        alt={genus.name} // Use genus name for alt text
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
                  {/* Revert color classes on genus name */}
                  <h2 
                    className="text-base font-semibold truncate italic text-center"
                    title={genus.name}
                  >
                    {genus.name}
                  </h2>
                  {/* Remove common name paragraph */}
                  {/* <p className="text-sm text-gray-600 dark:text-gray-400 truncate text-center" title={species.commonName}>{species.commonName}</p> */}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
} 