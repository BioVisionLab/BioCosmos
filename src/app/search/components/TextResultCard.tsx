"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { fetchSpeciesThumbnail, fetchThumbnailById } from "@/lib/images";
import { cleanSpeciesName } from "@/lib/names";
import Link from "next/link";
import { ImageLoading } from "@/components/Loadings";
import { MlResultItems } from "@/lib/ml_search";
import { TaxonomyData } from "@/lib/speciesData";

// Image size matching the backend resizing
const IMAGE_SIZE = 128;
// Reusable component for displaying a species card (similar to GenusSpeciesClient)
function MLSearchResultCard({
  classification,
}: {
  classification: TaxonomyData;
}) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const fetchImage = async () => {
      try {
        const response = await fetchSpeciesThumbnail(classification.species);
        setImageUrl(response);
      } catch (error) {
        console.error("Error fetching similar species image:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchImage();
  }, [classification.species]);

  return (
    <div className="bg-gray-100 dark:bg-gray-700 rounded-2xl p-2 items-center justify-center text-center w-[160px]">
      {loading ? (
        <ImageLoading size={IMAGE_SIZE} />
      ) : (
        <Link href={`/species/${classification.species}`}>
          <Image
            src={imageUrl || `/api/image/${classification.species}`}
            alt={`Image of ${classification.species}`}
            width={IMAGE_SIZE}
            height={IMAGE_SIZE}
            className="mx-auto object-contain"
          />

          <h2 className="text-sm truncate text-center text-gray-400 italic mt-2">
            {cleanSpeciesName(classification.species)}
          </h2>
        </Link>
      )}
    </div>
  );
}

export default MLSearchResultCard;
