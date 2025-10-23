"use client";
import { SpecimenData, fetchSpecimenData } from "@/lib/specimens";
import { useEffect, useState } from "react";

export function SpecimenPage({ speciesName }: { speciesName: string }) {
  const [specimenData, setSpecimenData] = useState<SpecimenData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    const fetchData = async () => {
      try {
        const response = await fetchSpecimenData(speciesName);
        setSpecimenData(response);
      } catch (error) {
        // Handle error using next js error handling
        console.error("Error fetching specimen data:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [speciesName]);

  return (
    <div className="mt-4 p-4 border border-gray-300 dark:border-gray-600 rounded-lg bg-white/70 dark:bg-gray-800/70 backdrop-blur shadow">
      <h2 className="text-2xl font-semibold mb-4">Specimen Information</h2>
      {loading ? (
        <p>Loading specimen data...</p>
      ) : specimenData ? (
        <div>
          <p>
            <strong>Species:</strong> {specimenData.species}
          </p>
          <p>
            <strong>Image Count:</strong> {specimenData.imageCounts}
          </p>
        </div>
      ) : (
        <p>No specimen data available.</p>
      )}
    </div>
  );
}
