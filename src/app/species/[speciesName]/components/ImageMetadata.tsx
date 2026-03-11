"use client";
import React from "react";
import { NoData } from "@/components/NoData";

interface ImageMetadataProps {
  speciesName?: string;
}

export default function ImageMetadata({ speciesName }: ImageMetadataProps) {
  return (
    <div className="p-4 bg-white dark:bg-gray-800 rounded shadow">
      <h2 className="text-lg font-semibold mb-2">Image Metadata</h2>
      <div className="text-sm text-gray-600 dark:text-gray-300">
        <NoData text={"No metadata available yet."} />
      </div>
    </div>
  );
}
