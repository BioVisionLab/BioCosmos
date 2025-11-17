"use client";
import { fetchSpeciesImageUmap, SpeciesImageUmap } from "@/lib/speciesData";
import { useEffect, useState } from "react";

function ImageUmap({ species }: { species: string }) {
  const [umapCoords, setUmapCoords] = useState<SpeciesImageUmap[] | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUmapData = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchSpeciesImageUmap(species);
        if (data) {
          setUmapCoords(data);
        } else {
          setError("No UMAP data found for this species.");
        }
      } catch (err) {
        setError("Error fetching UMAP data.");
      } finally {
        setLoading(false);
      }
    };

    fetchUmapData();
  }, [species]);

  if (loading) {
    return <div>Loading UMAP data...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  if (!umapCoords) {
    return <div>No UMAP data available.</div>;
  }

  return (
    <div>
      <h3>UMAP Embeddings for {species}</h3>
      <ul>
        {umapCoords.map((point) => (
          <li key={point.imgId}>
            Image ID: {point.imgId}, UMAP X: {point.umapX}, UMAP Y:{" "}
            {point.umapY}, Cluster: {point.clusterLabel ?? "N/A"}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ImageUmap;
