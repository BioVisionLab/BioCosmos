"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import type { CSSProperties } from "react";

import type { CountryDiversity } from "@/lib/countryDiversity";
import { speciesScale, stepLabels } from "@/components/map/speciesScale";

/** Fixed, so the page does not move when the map (or its failure) arrives. */
const MAP_HEIGHT = "h-[300px] sm:h-[400px] lg:h-[460px]";
const MAP_FRAME = `${MAP_HEIGHT} w-full overflow-hidden rounded-xl border border-deep-mocha-200 dark:border-deep-mocha-700 bg-deep-mocha-50 dark:bg-deep-mocha-900`;

function MapPlaceholder({ text }: { text: string }) {
  return (
    <div className={`${MAP_FRAME} flex items-center justify-center`}>
      <p className="text-sm text-deep-mocha-500 dark:text-deep-mocha-400">{text}</p>
    </div>
  );
}

// MapLibre needs `window`; it is loaded in the browser only.
const CountryDiversityMap = dynamic(
  () => import("@/components/map/CountryDiversityMap"),
  { ssr: false, loading: () => <MapPlaceholder text="Loading map…" /> },
);

/**
 * A swatch that carries both theme colours and lets the `dark:` variant pick,
 * so the server-rendered legend matches the client whatever the theme.
 */
function Swatch({
  light,
  dark,
  className,
}: {
  light: string;
  dark: string;
  className: string;
}) {
  return (
    <span
      className={`${className} bg-[var(--swatch-light)] dark:bg-[var(--swatch-dark)]`}
      style={{ "--swatch-light": light, "--swatch-dark": dark } as CSSProperties}
      aria-hidden="true"
    />
  );
}

function Legend({ data }: { data: CountryDiversity }) {
  const light = speciesScale(data.countries, false);
  const dark = speciesScale(data.countries, true);
  const labels = stepLabels(light.breaks);
  const middle = Math.floor(light.colors.length / 2);
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-deep-mocha-600 dark:text-deep-mocha-400">
      <div className="flex items-center gap-2">
        <span className="font-medium text-deep-mocha-700 dark:text-deep-mocha-300">
          Species
        </span>
        <ol className="flex" aria-label="Species per country colour scale">
          {labels.map((label, index) => (
            <li key={label} className="flex flex-col items-center">
              <Swatch
                className="h-2.5 w-10 sm:w-12"
                light={light.colors[index]}
                dark={dark.colors[index]}
              />
              <span className="mt-1 tabular-nums">{label}</span>
            </li>
          ))}
        </ol>
      </div>
      <div className="flex items-center gap-1.5">
        <Swatch
          className="h-2.5 w-4 rounded-sm border border-deep-mocha-300 dark:border-deep-mocha-600"
          light={light.noData}
          dark={dark.noData}
        />
        No validated records
      </div>
      <div className="flex items-center gap-1.5">
        <Swatch
          className="h-2.5 w-2.5 rounded-full border border-deep-mocha-800 dark:border-deep-mocha-100"
          light={light.colors[middle]}
          dark={dark.colors[middle]}
        />
        Territory shown by marker
      </div>
    </div>
  );
}

/**
 * Species diversity by validated country: the map, its legend, and the
 * caption the data summary notebook prints under panel G.
 *
 * Every state renders at the same height, so the section can stream in
 * without moving what is below it.
 */
export default function CountryDiversityPanel({
  data,
  pending = false,
  tableLink = true,
}: {
  data: CountryDiversity | null;
  pending?: boolean;
  tableLink?: boolean;
}) {
  const hasData = data !== null && data.countries.length > 0;
  return (
    <div>
      {hasData ? (
        <CountryDiversityMap countries={data.countries} className={`${MAP_FRAME} umap-dark-map`} />
      ) : (
        <MapPlaceholder
          text={pending ? "Loading map…" : "Country data is temporarily unavailable."}
        />
      )}

      {/* Legend and caption keep their lines whatever the state. */}
      <div className="min-h-[4.5rem]">
        {hasData && <Legend data={data} />}
        <p className="mt-2 text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
          {hasData
            ? `${data.mappedImages.toLocaleString("en-US")} images with a validated country (${data.imputedImages.toLocaleString("en-US")} imputed from coordinates) across ${data.countries.length.toLocaleString("en-US")} countries and territories. Hover a country for its counts; click it for its species.`
            : " "}
        </p>
      </div>
      {tableLink && (
        <p className="mt-1 text-sm">
          <Link
            href="/collections/country"
            className="text-pacific-blue-600 dark:text-pacific-blue-400 hover:underline"
          >
            Browse all countries →
          </Link>
        </p>
      )}
    </div>
  );
}
