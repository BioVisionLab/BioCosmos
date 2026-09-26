import { TextLoading } from "@/components/Loadings";

export const MAP_HEIGHT_PX = 400;

/**
 * The distribution card before it has anything to draw.
 *
 * One placeholder for all three waits — the card not yet scrolled into view,
 * the MapLibre bundle loading, and the occurrence requests in flight — laid
 * out exactly as the finished card: the same header, two legend rows and a
 * map of the same height. The previous placeholders were a bare 16:9 box and
 * then a smaller one inset in the card, so the column jumped twice before the
 * map appeared. Kept apart from the card itself so the dynamic import's
 * fallback can render it without pulling in the map.
 */
export function DistributionMapSkeleton({ msg }: { msg?: string }) {
  return (
    <div
      className="bg-linear-to-r from-white/50 to-white/30 dark:from-pacific-blue-900/30 dark:to-deep-mocha-800/50 rounded-xl backdrop-blur-lg"
      aria-busy="true"
    >
      <div className="bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-t-xl">
        <h2 className="text-2xl font-semibold">Distribution Map</h2>
      </div>
      <div className="px-4 py-3 space-y-2 animate-pulse" aria-hidden>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-deep-mocha-300 dark:bg-deep-mocha-600" />
          <span className="h-2.5 w-40 rounded bg-deep-mocha-200 dark:bg-deep-mocha-700" />
        </div>
        <div className="flex items-center gap-2">
          <span className="w-6 h-2.5 rounded-sm bg-deep-mocha-300 dark:bg-deep-mocha-600" />
          <span className="h-2.5 w-52 rounded bg-deep-mocha-200 dark:bg-deep-mocha-700" />
        </div>
      </div>
      <MapAreaPlaceholder msg={msg} />
    </div>
  );
}

/**
 * The map's footprint: a faint graticule so it reads as a map-to-be rather
 * than an empty box, with the message centred on it.
 */
export function MapAreaPlaceholder({ msg }: { msg?: string }) {
  return (
    <div
      className="relative overflow-hidden rounded-b-xl bg-deep-mocha-100/70 dark:bg-deep-mocha-800/60 flex items-center justify-center"
      style={{ height: MAP_HEIGHT_PX }}
    >
      <svg
        aria-hidden
        className="absolute inset-0 w-full h-full text-deep-mocha-300/60 dark:text-deep-mocha-600/50 animate-pulse"
        viewBox="0 0 360 180"
        preserveAspectRatio="none"
      >
        {[30, 60, 90, 120, 150].map((y) => (
          <line
            key={`lat-${y}`}
            x1="0"
            x2="360"
            y1={y}
            y2={y}
            stroke="currentColor"
            strokeWidth="0.4"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {[45, 90, 135, 180, 225, 270, 315].map((x) => (
          <line
            key={`lon-${x}`}
            y1="0"
            y2="180"
            x1={x}
            x2={x}
            stroke="currentColor"
            strokeWidth="0.4"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      {msg && (
        <div className="relative rounded-full bg-white/80 dark:bg-deep-mocha-900/80 px-4 py-2 shadow-sm">
          <TextLoading msg={msg} />
        </div>
      )}
    </div>
  );
}
