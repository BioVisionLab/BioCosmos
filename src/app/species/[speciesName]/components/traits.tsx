import { LepTraits } from "@/lib/speciesData";
import { useEffect, useRef } from "react";

function SpeciesTraits({ traits }: { traits: LepTraits | null }) {
  if (!traits) {
    return <p className="text-gray-200">No traits available.</p>;
  }

  return (
    <div>
      <ul className="list-disc list-inside">
        {Object.entries(traits)
          .filter(([, value]) => value != null && value !== "")
          .map(([key, value]) => (
            <li key={key} className="text-gray-200">
              <span className="font-medium">{key.replace(/_/g, " ")}:</span>{" "}
              {value}
            </li>
          ))}
      </ul>
    </div>
  );
}

function MonthPresence({ traits }: { traits: LepTraits | null }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  if (!traits) {
    return null;
  }

  useEffect(() => {
    const ctx = canvasRef.current?.getContext("2d");

    const chart = new Chart(ctx!, {
      type: "bar",
      data: {
        labels: Object.keys(traits.month_presence || {}),
        datasets: [
          {
            label: "Month Presence",
            data: Object.values(traits.month_presence || {}).map((v) =>
              v ? 1 : 0
            ),
            backgroundColor: "rgba(75, 192, 192, 0.6)",
          },
        ],
      },
      options: {
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              stepSize: 1,
              callback: (value) => (value === 1 ? "Yes" : "No"),
            },
          },
        },
      },
    });

    return () => {
      chart.destroy();
    };
  }, [traits]);

  return (
    <div>
      <h3 className="text-lg font-semibold text-gray-300">Month Presence</h3>
      <ul className="list-disc list-inside">
        {months.map((month) => (
          <li key={month} className="text-gray-200">
            <span className="font-medium">{month}:</span>{" "}
            {traits.month_presence[month] ? "Yes" : "No"}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default SpeciesTraits;
