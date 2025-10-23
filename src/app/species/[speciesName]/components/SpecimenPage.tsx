"use client";
import { ImageLoading } from "@/components/Loadings";
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
    <>
      {loading ? (
        <ImageLoading size={240} msg="Hang tight! Fetching specimen data" />
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
    </>
  );
}
