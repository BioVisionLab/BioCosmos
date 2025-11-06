"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { fetchThumbnailById } from "@/lib/images";
import { cleanSpeciesName } from "@/lib/names";
import Link from "next/link";
import { ImageLoading } from "@/components/Loadings";
import { SemanticResultItem } from "@/lib/ml_search";

// Image size matching the backend resizing
const IMAGE_SIZE = 128;
// Reusable component for displaying a species card (similar to GenusSpeciesClient)
function SpeciesSearchResultCard({ species }: { species: SemanticResultItem }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const fetchImage = async () => {
      try {
        const response = await fetchThumbnailById(species.imgId);
        setImageUrl(response);
      } catch (error) {
        console.error("Error fetching similar species image:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchImage();
  }, [species.imgId]);

  const speciesName = cleanSpeciesName(species.species);

  return (
    <div className="bg-gray-100 dark:bg-gray-700 rounded-2xl p-2 items-center justify-center text-center w-[160px]">
      {loading ? (
        <ImageLoading size={IMAGE_SIZE} />
      ) : (
        <Link href={`/species/${species.species}`}>
          <Image
            src={imageUrl || `/api/image/${species.imgId}`}
            alt={`Image of ${species.species}`}
            width={IMAGE_SIZE}
            height={IMAGE_SIZE}
            className="mx-auto object-contain"
          />

          <h2 className="text-sm truncate text-center text-gray-400 italic mt-2">
            {speciesName}
          </h2>
          <p className="text-xs text-gray-500">
            Scores: {species.distance.toPrecision(3)}
          </p>
        </Link>
      )}
    </div>
  );
}

export default SpeciesSearchResultCard;
