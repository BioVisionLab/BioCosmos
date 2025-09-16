import { LepTraits } from "@/lib/speciesData";
// import { Chart } from "chart.js/auto";
import { Plane, Target, Trees } from "lucide-react";

const valueClass =
  "font-semibold text-emerald-600 dark:text-emerald-300 text-xl";

function SpeciesTraits({ traits }: { traits: LepTraits | null }) {
  if (!traits) {
    return <p className="text-gray-200">No traits available.</p>;
  }
  const containerClasses = "my-4 relative rounded-xl p-2 overflow-hidden";
  const boxClasses = containerClasses.replace("my-4", "");

  return (
    <div className="grid gap-2 md:grid-cols-2 transition-all p-2">
      <div className={`${boxClasses} md:col-span-2 h-fit`}>
        <h3 className="text-xl m-2">Wingspan</h3>
        <div className="space-y-2">
          <WingspanCard
            upper_male={traits.wingspan_upper_male}
            upper_female={traits.wingspan_upper_female}
            upper_unspecified={traits.wingspan_upper_unspecified}
            lower_male={traits.wingspan_lower_male}
            lower_female={traits.wingspan_lower_female}
            lower_unspecified={traits.wingspan_lower_unspecified}
          />
        </div>
      </div>

      {/* Each small card is its own grid item (no wrapping flex) */}
      {typeof traits.flight_duration === "number" &&
        !Number.isNaN(traits.flight_duration) && (
          <div className={boxClasses}>
            <h3 className="text-xl m-2">Flight Duration</h3>
            <FlightDuration duration={traits.flight_duration} />
          </div>
        )}

      {typeof traits.canopy_affinity === "string" &&
        traits.canopy_affinity.trim() !== "" && (
          <div className={boxClasses}>
            <h3 className="text-xl m-2">Canopy Affinity</h3>
            <CanopyAffinity affinity={traits.canopy_affinity} />
          </div>
        )}
      <ul>
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

// function MonthPresence({ traits }: { traits: LepTraits | null }) {
//   const canvasRef = useRef<HTMLCanvasElement | null>(null);
//   if (!traits) {
//     return null;
//   }

//   useEffect(() => {
//     const ctx = canvasRef.current?.getContext("2d");

//     const chart = new Chart(ctx!, {
//       type: "bar",
//       data: {
//         labels: Object.keys(traits.month_presence || {}),
//         datasets: [
//           {
//             label: "Month Presence",
//             data: Object.values(traits.month_presence || {}).map((v) =>
//               v ? 1 : 0
//             ),
//             backgroundColor: "rgba(75, 192, 192, 0.6)",
//           },
//         ],
//       },
//       options: {
//         scales: {
//           y: {
//             beginAtZero: true,
//             ticks: {
//               stepSize: 1,
//               callback: (value) => (value === 1 ? "Yes" : "No"),
//             },
//           },
//         },
//       },
//     });

//     return () => {
//       chart.destroy();
//     };
//   }, [traits]);

//   return (
//     <div>
//       <h3 className="text-lg font-semibold text-gray-300">Month Presence</h3>
//       <ul className="list-disc list-inside">
//         {months.map((month) => (
//           <li key={month} className="text-gray-200">
//             <span className="font-medium">{month}:</span>{" "}
//             {traits.month_presence[month] ? "Yes" : "No"}
//           </li>
//         ))}
//       </ul>
//     </div>
//   );
// }

function WingspanCard({
  upper_male,
  upper_female,
  upper_unspecified,
  lower_male,
  lower_female,
  lower_unspecified,
}: {
  upper_male: number | null | undefined;
  upper_female: number | null | undefined;
  upper_unspecified: number | null | undefined;
  lower_male: number | null | undefined;
  lower_female: number | null | undefined;
  lower_unspecified: number | null | undefined;
}) {
  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Target className="h-32 w-32" />
      </div>
      <div className="space-y-2 ml-4">
        <div>
          <h3 className="text-lg leading-tight">Upper</h3>
          {upper_male || upper_female || upper_unspecified ? (
            <Wingspan
              male={upper_male}
              female={upper_female}
              unspecified={upper_unspecified}
            />
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No wingspan data available.
            </p>
          )}
        </div>
        <div>
          <h3 className="text-lg leading-tight">Lower</h3>
          {lower_male || lower_female || lower_unspecified ? (
            <Wingspan
              male={lower_male}
              female={lower_female}
              unspecified={lower_unspecified}
            />
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No wingspan data available.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Wingspan({
  male,
  female,
  unspecified,
}: {
  male: number | null | undefined;
  female: number | null | undefined;
  unspecified: number | null | undefined;
}) {
  const hasValue = (v: unknown): v is number =>
    typeof v === "number" && !Number.isNaN(v);

  if (![male, female, unspecified].some(hasValue)) {
    return null;
  }

  return (
    <ul className="space-y-1 text-gray-700 dark:text-gray-300">
      {hasValue(male) && (
        <li>
          <span className={valueClass}>{male} cm</span>
          <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mr-1">
            {" (♂)"}
          </span>
        </li>
      )}
      {hasValue(female) && (
        <li>
          <span className={valueClass}>{female} cm</span>
          <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mr-1">
            {" (♀)"}
          </span>
        </li>
      )}
      {hasValue(unspecified) && (
        <li>
          <span className={valueClass}>{unspecified} cm</span>
          <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mr-1">
            {" (Unspecified)"}
          </span>
        </li>
      )}
    </ul>
  );
}

function FlightDuration({ duration }: { duration: number | null | undefined }) {
  const hasValue = (v: unknown): v is number =>
    typeof v === "number" && !Number.isNaN(v);

  if (!hasValue(duration)) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Plane className="h-12 w-12" />
      </div>
      <div>
        <p className={valueClass}>
          {duration} month{duration === 1 ? "" : "s"}
        </p>
      </div>
    </div>
  );
}

function CanopyAffinity({ affinity }: { affinity: string | null | undefined }) {
  const hasValue = (v: unknown): v is string =>
    typeof v === "string" && v.trim() !== "";

  if (!hasValue(affinity)) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Trees className="h-12 w-12" />
      </div>
      <div>
        <p className={valueClass}>{affinity}</p>
      </div>
    </div>
  );
}

export { SpeciesTraits, WingspanCard, FlightDuration, CanopyAffinity };
