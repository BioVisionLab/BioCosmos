"use client";

import React from "react";
import SpecimensTab from "./SpecimensTab";
import SpeciesHeader from "./SpeciesTitle";
import { TaxonomyData } from "@/lib/speciesData";

interface SpecimenGalleryProps {
  speciesName?: string;
  /** Fetched by the gallery route on the server; null when unavailable. */
  taxonomy: TaxonomyData | null;
}

export default function SpecimenGallery({
  speciesName,
  taxonomy,
}: SpecimenGalleryProps) {
  return (
    <div>
      {taxonomy ? (
        <SpeciesHeader taxonomy={taxonomy} name={taxonomy.species ?? ""} />
      ) : null}
      <SpecimensTab
        speciesName={speciesName}
        showAll={true}
        showMorphospace={false}
        showImageCount={false}
      />
    </div>
  );
}
