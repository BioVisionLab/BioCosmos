"use client";

import React from "react";
import SpecimensTab from "./SpecimensTab";

interface SpecimenGalleryProps {
  speciesName?: string;
}

export default function SpecimenGallery({ speciesName }: SpecimenGalleryProps) {
  // Render the full gallery (SpecimensTab will fetch all IDs when showAll is true)
  return <SpecimensTab speciesName={speciesName} showAll={true} showUmap={false} />;
}
