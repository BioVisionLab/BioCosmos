import { GlobeControl } from "maplibre-gl";
import type { Map as MapLibreMap, StyleSwapOptions } from "maplibre-gl";

// Kept apart from `map.ts`: that module is also reached from server code,
// and this one pulls in maplibre-gl at runtime.

/**
 * Add the globe toggle under a map's zoom buttons.
 *
 * Every geographic map opens on Web Mercator, the projection readers know,
 * and the toggle turns it into a globe on request — where species ranges and
 * country areas are not inflated towards the poles the way Mercator draws
 * them. MapLibre blends a globe back into Mercator by itself as the reader
 * zooms in, so street-level detail is the same either way.
 *
 * Equal Earth, the equal-area projection one would print, is not among
 * MapLibre's projections (mercator, globe and vertical-perspective only),
 * and reprojecting the vector basemap would mean replacing MapLibre.
 *
 * Add it after the NavigationControl so the two stack in one column.
 */
function addProjectionToggle(map: MapLibreMap): void {
  map.addControl(new GlobeControl(), "top-right");
}

/**
 * `setStyle` options that carry the reader's projection over to the new
 * style.
 *
 * The projection belongs to the style, so a theme switch — which swaps the
 * whole basemap — would otherwise put a globe back on Mercator.
 *
 * Read here, when the swap is requested, not inside `transformStyle`: by the
 * time MapLibre calls that, it has already installed the new, empty style,
 * and the map reports that style's default Mercator.
 */
function keepProjection(map: MapLibreMap): StyleSwapOptions {
  const projection = map.getProjection();
  return {
    transformStyle: (_previous, next) => ({
      ...next,
      projection: projection ?? next.projection,
    }),
  };
}

export { addProjectionToggle, keepProjection };
