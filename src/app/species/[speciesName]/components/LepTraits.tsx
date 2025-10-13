import {
  LepTraits,
  parseDiapauseStage,
  parseMonthPresence,
  parseOvipositionStyle,
  parseVoltinism,
} from "@/lib/leptraits";

// import { Chart } from "chart.js/auto";
import { Circle, Egg, Plane, Target, Trees } from "lucide-react";
import { useMemo } from "react";
import { PolarArea } from "react-chartjs-2";

import {
  Chart as ChartJS,
  RadialLinearScale,
  ArcElement,
  Tooltip,
  Legend,
} from "chart.js";
import {
  LepTraitDataSourceInfo,
  LepTraitsAttribution,
} from "@/components/Attribution";

ChartJS.register(RadialLinearScale, ArcElement, Tooltip, Legend);

const valueClass =
  "font-semibold text-emerald-600 dark:text-emerald-300 text-xl";
const labelClass = "font-normal text-gray-500 dark:text-gray-300";

function SpeciesTraits({ traits }: { traits: LepTraits | null }) {
  if (!traits) {
    return <p className="text-gray-200">No traits available.</p>;
  }
  const containerClasses = "relative rounded-xl p-2 overflow-hidden";
  const boxClasses = containerClasses.replace("my-2", "");
  const lineClasses = "border-t border-gray-300 dark:border-gray-700 my-2";
  const gridClasses = "grid gap-2 md:grid-cols-2 transition-all mb-4";
  return (
    <div>
      <h2 className="text-2xl font-bold">Morphology</h2>
      <div className={lineClasses} />
      <div className={gridClasses}>
        <div className={`${boxClasses} md:col-span-2 h-fit`}>
          <h3 className="text-xl">Wingspan</h3>
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
      </div>
      <h2 className="text-2xl font-bold mt-4">Life History</h2>
      <div className={lineClasses} />
      <div className={gridClasses}>
        {/* Each small card is its own grid item (no wrapping flex) */}
        {typeof traits.voltinism === "string" &&
          traits.voltinism.trim() !== "" && (
            <div className={boxClasses}>
              <h3 className="text-xl m-2">Voltinism</h3>
              <Voltinism voltinism={traits.voltinism} />
            </div>
          )}
        {typeof traits.diapause_stage === "string" &&
          traits.diapause_stage.trim() !== "" && (
            <div className={boxClasses}>
              <h3 className="text-xl m-2">Diapause Stage</h3>
              <DiapauseStage diapause={traits.diapause_stage} />
            </div>
          )}
        {typeof traits.oviposition_style === "string" &&
          traits.oviposition_style.trim() !== "" && (
            <div className={boxClasses}>
              <h3 className="text-xl m-2">Oviposition Style</h3>
              <OvipositionStyle style={traits.oviposition_style} />
            </div>
          )}
      </div>
      <h2 className="text-2xl font-bold mt-4">Habitats</h2>
      <div className={lineClasses} />
      {typeof traits.canopy_affinity === "string" &&
        traits.canopy_affinity.trim() !== "" && (
          <div className={boxClasses}>
            <h3 className="text-xl m-2">Canopy Affinity</h3>
            <Affinity affinity={traits.canopy_affinity} />
          </div>
        )}
      {typeof traits.edge_affinity === "string" &&
        traits.edge_affinity.trim() !== "" && (
          <div className={boxClasses}>
            <h3 className="text-xl m-2">Edge Affinity</h3>
            <Affinity affinity={traits.edge_affinity} />
          </div>
        )}
      {typeof traits.moisture_affinity === "string" &&
        traits.moisture_affinity.trim() !== "" && (
          <div className={boxClasses}>
            <h3 className="text-xl m-2">Moisture Affinity</h3>
            <Affinity affinity={traits.moisture_affinity} />
          </div>
        )}
      {typeof traits.disturbance_affinity === "string" &&
        traits.disturbance_affinity.trim() !== "" && (
          <div className={boxClasses}>
            <h3 className="text-xl m-2">Disturbance Affinity</h3>
            <Affinity affinity={traits.disturbance_affinity} />
          </div>
        )}
      <h2 className="text-2xl font-bold mt-4">Resources</h2>
      <div className={lineClasses} />
      <div className={gridClasses}>
        {/* Each small card is its own grid item (no wrapping flex) */}
        {typeof traits.number_of_hostplant_families === "number" &&
          !Number.isNaN(traits.number_of_hostplant_families) && (
            <div className={boxClasses}>
              <h3 className="text-xl m-2">Number of Host Plant Families</h3>
              <NumberOfHostPlants count={traits.number_of_hostplant_families} />
            </div>
          )}
        {typeof traits.sole_hostplant_family === "string" &&
          traits.sole_hostplant_family.trim() !== "" && (
            <div className={boxClasses}>
              <h3 className="text-xl m-2">Sole Host Plant Family</h3>
              <HostPlantFamilies families={traits.sole_hostplant_family} />
            </div>
          )}
        {typeof traits.primary_hostplant_family === "string" &&
          traits.primary_hostplant_family.trim() !== "" && (
            <div className={boxClasses}>
              <h3 className="text-xl m-2">Primary Host Plant Family</h3>
              <HostPlantFamilies families={traits.primary_hostplant_family} />
            </div>
          )}
        {typeof traits.secondary_hostplant_family === "string" &&
          traits.secondary_hostplant_family.trim() !== "" && (
            <div className={boxClasses}>
              <h3 className="text-xl m-2">Secondary Host Plant Family</h3>
              <HostPlantFamilies families={traits.secondary_hostplant_family} />
            </div>
          )}
        {typeof traits.equal_hostplant_family === "string" &&
          traits.equal_hostplant_family.trim() !== "" && (
            <div className={boxClasses}>
              <h3 className="text-xl m-2">Equal Host Plant Family</h3>
              <HostPlantFamilies families={traits.equal_hostplant_family} />
            </div>
          )}
        {typeof traits.number_of_hostplant_accounts === "number" &&
          !Number.isNaN(traits.number_of_hostplant_accounts) && (
            <div className={boxClasses}>
              <h3 className="text-xl m-2">Number of Host Plant Accounts</h3>
              <HostPlantAccount count={traits.number_of_hostplant_accounts} />
            </div>
          )}
      </div>
      <h2 className="text-2xl font-bold mt-4">Phenology</h2>
      <div className={lineClasses} />
      {typeof traits.flight_duration === "number" &&
        !Number.isNaN(traits.flight_duration) && (
          <div className={boxClasses}>
            <h3 className="text-xl">Flight Duration</h3>
            <FlightDuration duration={traits.flight_duration} />
          </div>
        )}
      <div className={boxClasses}>
        <h3 className="text-xl">Adult Presence by Month</h3>
        <MonthPresence traits={traits} />
      </div>
      <LepTraitDataSourceInfo />
    </div>
  );
}

function MonthPresence({ traits }: { traits: LepTraits | null }) {
  if (!traits) {
    return null;
  }

  const presentAbsentMap = useMemo(() => parseMonthPresence(traits), [traits]);

  // Only render if we have data
  if (Object.keys(presentAbsentMap).length === 0) {
    return null;
  }

  const labels = Object.keys(presentAbsentMap);
  const values = Object.values(presentAbsentMap);

  // Create background colors - green for present, light gray for absent
  const backgroundColors = values.map((v) =>
    v ? "rgba(134, 239, 172, 0.8)" : "rgba(229, 231, 235, 0.3)"
  );

  const data = {
    labels: labels,
    datasets: [
      {
        label: "Adult Presence",
        data: Array(labels.length).fill(1), // All segments same size
        backgroundColor: backgroundColors,
        borderColor: "rgba(107, 114, 128, 0.5)",
        borderWidth: 1,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: function (context: any) {
            const month = context.label;
            const isPresent = values[context.dataIndex];
            return `${month}: ${isPresent ? "Present" : "Absent"}`;
          },
        },
      },
    },
    scales: {
      r: {
        beginAtZero: true,
        max: 1,
        ticks: {
          display: false, // Hide radial ticks
          stepSize: 0.5,
        },
        grid: {
          color: "rgba(209, 213, 219, 0.3)",
        },
        pointLabels: {
          font: {
            size: 12,
          },
          color: "#ff0000",
        },
      },
    },
  };

  return (
    <div>
      <div className="w-full h-64 flex mt-4">
        <PolarArea data={data} options={options} />
      </div>
    </div>
  );
}

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
          <span className={labelClass}>{" (♂)"}</span>
        </li>
      )}
      {hasValue(female) && (
        <li>
          <span className={valueClass}>{female} cm</span>
          <span className={labelClass}>{" (♀)"}</span>
        </li>
      )}
      {hasValue(unspecified) && (
        <li>
          <span className={valueClass}>{unspecified} cm</span>
          <span className={labelClass}>{" (Unspecified)"}</span>
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

function Affinity({ affinity }: { affinity: string | null | undefined }) {
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

function Voltinism({ voltinism }: { voltinism: string | null | undefined }) {
  const hasValue = (v: unknown): v is string =>
    typeof v === "string" && v.trim() !== "";

  if (!hasValue(voltinism)) {
    return null;
  }

  const voltinismLabel = parseVoltinism(voltinism);

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Circle className="h-12 w-12 m-1" />
      </div>
      <p className={valueClass}>
        {voltinismLabel.label}{" "}
        {voltinismLabel.description.trim() === "" ? null : (
          <span className={labelClass}>
            {voltinismLabel.description.trim()}
          </span>
        )}
      </p>
    </div>
  );
}

function DiapauseStage({ diapause }: { diapause: string | null | undefined }) {
  const hasValue = (v: unknown): v is string =>
    typeof v === "string" && v.trim() !== "";

  if (!hasValue(diapause)) {
    return null;
  }

  const diapauseLabel = parseDiapauseStage(diapause);

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Egg className="h-12 w-12" />
      </div>
      <p className={valueClass}>
        {diapauseLabel.label}{" "}
        {diapauseLabel.description.trim() === "" ? null : (
          <span className={labelClass}>{diapauseLabel.description.trim()}</span>
        )}
      </p>
    </div>
  );
}

function OvipositionStyle({ style }: { style: string | null | undefined }) {
  const hasValue = (v: unknown): v is string =>
    typeof v === "string" && v.trim() !== "";

  if (!hasValue(style)) {
    return null;
  }

  const styleLabel = parseOvipositionStyle(style);

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Egg className="h-12 w-12" />
      </div>
      <p className={valueClass}>{styleLabel}</p>
    </div>
  );
}

function NumberOfHostPlants({ count }: { count: number | null | undefined }) {
  const hasValue = (v: unknown): v is number =>
    typeof v === "number" && !Number.isNaN(v);

  if (!hasValue(count)) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Circle className="h-12 w-12 m-1" />
      </div>
      <div>
        <p className={valueClass}>
          {count}
          <span className={labelClass}>
            {" "}
            {count > 1 ? " families" : " family"}
          </span>
        </p>
      </div>
    </div>
  );
}

function HostPlantFamilies({
  families,
}: {
  families: string | null | undefined;
}) {
  const hasValue = (v: unknown): v is string =>
    typeof v === "string" && v.trim() !== "";

  if (!hasValue(families)) {
    return null;
  }

  // Split by commas and trim whitespace
  const familyList = families.split(",").map((f) => f.trim());

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Circle className="h-12 w-12 m-1" />
      </div>
      <div>
        <p className={valueClass}>{familyList.join(" · ")}</p>
      </div>
    </div>
  );
}

function HostPlantAccount({ count }: { count: number | null | undefined }) {
  const hasValue = (v: unknown): v is number =>
    typeof v === "number" && !Number.isNaN(v);

  if (!hasValue(count)) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Circle className="h-12 w-12 m-1" />
      </div>
      <div>
        <p className={valueClass}>
          {count} <span className={labelClass}>host plant account</span>
        </p>
      </div>
    </div>
  );
}

export { SpeciesTraits, WingspanCard, FlightDuration, Affinity, Voltinism };
