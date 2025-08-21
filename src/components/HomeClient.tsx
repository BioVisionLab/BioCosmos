"use client"; // Mark this component as a Client Component

import React, { useState, useEffect } from "react";
import Image from "next/image";
import {
  getSpeciesList,
  fetchSpeciesImage,
  SpeciesThumbnails,
} from "@/lib/speciesList";

export default function HomeClient() {
  const [speciesThumbnails, setSpeciesThumbnails] = useState<string | null>(
    null
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSpeciesThumbnails = async () => {
      try {
        const res = await fetch(
          "http://127.0.0.1:8000/taxon/zischkaia_pacarus/thumbnail"
        );
        const data = await res.blob();
        const imageUrl = URL.createObjectURL(data);
        setSpeciesThumbnails(imageUrl);
      } catch (error) {
        console.error("Failed to fetch species thumbnails:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchSpeciesThumbnails();
  }, []); // Empty dependency array ensures this runs only once on mount

  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-4xl font-bold mb-8">Welcome to BioCosmos</h1>
      {loading ? (
        <p>Loading species thumbnails...</p>
      ) : speciesThumbnails ? (
        <Image
          src={speciesThumbnails}
          alt="Species Thumbnail"
          width={300}
          height={300}
          className="rounded-lg shadow-lg"
        />
      ) : (
        <p>No species thumbnails available.</p>
      )}
    </div>
  );
}
