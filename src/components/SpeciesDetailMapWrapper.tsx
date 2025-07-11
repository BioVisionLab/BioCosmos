"use client"; // This component needs to be a client component

import dynamic from "next/dynamic";
import React from "react";
import { GbifAttribution } from "./Attribution";

// Define Occurrence type again (or import if shared)
interface Occurrence {
  key: string | number;
  decimalLatitude: number;
  decimalLongitude: number;
}

// Dynamically import the map component within the client component
const SpeciesMap = dynamic(() => import("@/components/SpeciesMap"), {
  ssr: false, // Allowed here because this wrapper is a client component
  loading: () => (
    <div className="aspect-video bg-gray-200 dark:bg-gray-700 rounded flex items-center justify-center">
      <span className="text-gray-500">Loading map...</span>
    </div>
  ),
});

interface MapWrapperProps {
  occurrences: Occurrence[];
}

const SpeciesDetailMapWrapper: React.FC<MapWrapperProps> = ({
  occurrences,
}) => {
  return (
    <div>
      <SpeciesMap occurrences={occurrences} />
      <GbifAttribution leadingText="Occurrence data provided by" />
    </div>
  );
};

export default SpeciesDetailMapWrapper;
