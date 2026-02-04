"use client";

import React, { useEffect, useState } from "react";
import SpecimensTab from "./SpecimensTab";
import SpeciesHeader from "./SpeciesTitle";

interface SpecimenGalleryProps {
  speciesName?: string;
}

export default function SpecimenGallery({ speciesName }: SpecimenGalleryProps) {
  // Try to reuse species data cached by the main species page to avoid refetching.
  const [speciesData, setSpeciesData] = useState<any | null>(null);

  useEffect(() => {
    if (!speciesName) return;
    try {
      const raw = localStorage.getItem(`speciesData:${speciesName}`);
      if (raw) setSpeciesData(JSON.parse(raw));
    } catch (e) {
      // ignore
    }
  }, [speciesName]);

  return (
    <div>
      {speciesData ? (
        <SpeciesHeader taxonomy={speciesData.taxonomy} name={speciesData.taxonomy?.species ?? ""} />
      ) : null}
      <SpecimensTab speciesName={speciesName} showAll={true} showUmap={false} showImageCount={false} />
    </div>
  );
}
