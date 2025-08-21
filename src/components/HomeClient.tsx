"use client"; // Mark this component as a Client Component

import React, { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { API_HOST } from "@/lib/config";
// Define the shape of our species data
interface SpeciesData {
  name: string;
  imageUrl: string | null;
}

// The list of initial species to display
const initialSpeciesList = [
  "zeuxidia_doubledaii",
  "abananote_erinome",
  "abrota_ganga",
  "zeuxidia_luxerii",
  "zipaetis_saitis",
  "acidalia_adela",
  "zipaetis_scylax",
  "zischkaia_pacarus",
];

export default function HomeClient() {
  const [speciesData, setSpeciesData] = useState<SpeciesData[]>([]);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    const fetchSpeciesData = async () => {
      const data: SpeciesData[] = await Promise.all(
        initialSpeciesList.map(async (speciesName) => {
          try {
            const response = await fetch(
              `${API_HOST}/taxon/${speciesName}/thumbnail`
            );
            if (response.ok) {
              const blob = await response.blob();
              const imageUrl = URL.createObjectURL(blob);
              return { name: speciesName, imageUrl };
            }
          } catch (error) {
            console.error(`Failed to fetch image for ${speciesName}:`, error);
          }
          return { name: speciesName, imageUrl: null };
        })
      );
      setSpeciesData(data);
    };

    fetchSpeciesData();
  }, []);

  const filteredSpecies = speciesData.filter((species) =>
    species.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <section>
      <div className="mb-6">
        <input
          type="text"
          placeholder="Filter species by name..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full md:w-1/2 px-4 py-2 rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-green-500"
        />
      </div>

      {filteredSpecies.length === 0 ? (
        <p className="text-gray-500">
          {searchTerm
            ? "No species found matching your filter."
            : "Loading species..."}
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {filteredSpecies.map((species, index) => (
            <Link
              key={index}
              href={`/species/${species.name}`}
              legacyBehavior={false}
            >
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
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
