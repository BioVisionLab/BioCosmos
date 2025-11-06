"use client";
import { IconContainer } from "@/components/IconContainer";
import { ImageLoading } from "@/components/Loadings";
import { ButterflyComplex } from "@/components/ui/Butterfly";
import { SpecimenData, fetchSpecimenData } from "@/lib/specimens";
import { formatNumberToLocaleString } from "@/lib/textUtils";
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
        <div className="flex flex-col-2 items-center">
          <IconContainer>
            <ButterflyComplex className="w-16 h-16 fill-teal-500" />
          </IconContainer>
          <div className="my-2 py-2">
            <p className="text-lg font-semibold">Image count</p>
            <p className="text-2xl font-semibold">
              {formatNumberToLocaleString(specimenData.imageCounts)}
            </p>
          </div>
        </div>
      ) : (
        <p>No specimen data available.</p>
      )}
    </>
  );
}
