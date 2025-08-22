"use client"; // Mark this component as a Client Component

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { SpeciesThumbnails, getInitialSpeciesList } from "@/lib/speciesList";

export default function HomeClient() {
  const [speciesList, setSpeciesList] = useState<SpeciesThumbnails[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSpeciesThumbnails = async () => {
      try {
        const speciesList = await getInitialSpeciesList();
        setSpeciesList(speciesList);
      } catch (error) {
        console.error("Failed to fetch species thumbnails:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchSpeciesThumbnails();
  }, []); // Empty dependency array ensures this runs only once on mount

  return (
    <div className="flex flex-col items-center min-h-screen">
      <h1 className="text-4xl font-bold mb-8">Welcome</h1>
      {loading ? (
        <p>Loading species thumbnails...</p>
      ) : speciesList.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mx-auto">
          {speciesList.map((thumbnail, index) => (
            <div key={index} className="flex flex-col items-center">
              <div className="flex justify-center bg-gray-100 dark:bg-gray-700">
                <Image
                  src={thumbnail.imageUrl}
                  alt={`Species Thumbnail ${index + 1}`}
                  width={150}
                  height={150}
                  className="m-2"
                />
              </div>
              <div className="mt-2 text-center">
                <h2
                  className="text-base font-semibold truncate italic text-center"
                  title={thumbnail.name}
                >
                  {thumbnail.name}
                </h2>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p>No species thumbnails available.</p>
      )}
    </div>
  );
}
