"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { MapLibreMap, NavigationControl, Popup } from "maplibre-gl";
import type {
  ExpressionSpecification,
  MapLayerMouseEvent,
  StyleSpecification,
} from "maplibre-gl";
import { useTheme } from "next-themes";
import "maplibre-gl/dist/maplibre-gl.css";
import { getBasemapAttribution, loadLightBasemapStyle } from "@/lib/map";
import { addProjectionToggle, keepProjection } from "@/lib/mapProjection";
import { configureMapLibreWorker } from "@/lib/maplibreWorker";
import { countryHref, type CountryDiversityRow } from "@/lib/countryDiversity";
import { speciesScale, type SpeciesScale } from "./speciesScale";

/**
 * Country polygons and small-territory markers, keyed by the ISO alpha-2 code
 * the shared harmonize-core lookup assigns. Written by
 * `backend/scripts/export_country_geometry.py`.
 */
const GEOMETRY_URL = "/geo/countries-110m.json";
const SOURCE_ID = "countries";
const FILL_LAYER = "countries-fill";
const HOVER_LAYER = "countries-hover";
const MARKER_LAYER = "countries-marker";

// A world thematic map has nothing to show past country scale, and every
// zoom level the reader cannot reach is a level of vector tiles never fetched.
const MAX_ZOOM = 5;
const WORLD: [[number, number], [number, number]] = [
  [-180, -58],
  [180, 78],
];

function colorExpression(scale: SpeciesScale): ExpressionSpecification {
  const step: unknown[] = [
    "step",
    ["feature-state", "species"],
    scale.colors[0],
  ];
  scale.breaks.slice(1).forEach((lower, index) => {
    step.push(lower, scale.colors[index + 1]);
  });
  return [
    "case",
    ["==", ["typeof", ["feature-state", "species"]], "number"],
    step as ExpressionSpecification,
    scale.noData,
  ];
}

function addCountryLayers(
  map: MapLibreMap,
  scale: SpeciesScale,
  isDark: boolean,
) {
  if (!map.getSource(SOURCE_ID)) {
    map.addSource(SOURCE_ID, {
      type: "geojson",
      data: GEOMETRY_URL,
      promoteId: "code",
      // The source is 110m-scale; tiling it past z4 only rebuilds the same
      // vertices at more zooms. MapLibre overzooms z4 for the rest.
      maxzoom: 4,
      tolerance: 0.6,
      buffer: 64,
    });
  }

  // Fills sit under the basemap's country borders, so borders stay crisp.
  const firstBoundary = map
    .getStyle()
    .layers.find((layer) => layer.id.startsWith("boundary"))?.id;
  const border = isDark ? "#1c1717" : "#ffffff";

  map.addLayer(
    {
      id: FILL_LAYER,
      type: "fill",
      source: SOURCE_ID,
      filter: ["!", ["has", "marker"]],
      paint: {
        "fill-color": colorExpression(scale),
        "fill-outline-color": border,
      },
    },
    firstBoundary,
  );
  map.addLayer({
    id: HOVER_LAYER,
    type: "line",
    source: SOURCE_ID,
    filter: ["!", ["has", "marker"]],
    paint: {
      "line-color": isDark ? "#f5f5f4" : "#1c1717",
      "line-width": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        1.5,
        0,
      ],
    },
  });
  map.addLayer({
    id: MARKER_LAYER,
    type: "circle",
    source: SOURCE_ID,
    filter: ["has", "marker"],
    paint: {
      "circle-color": colorExpression(scale),
      // Territories without records are not drawn at all; a radius of 0 also
      // keeps them out of hover hit-testing.
      "circle-radius": [
        "case",
        ["==", ["typeof", ["feature-state", "species"]], "number"],
        ["case", ["boolean", ["feature-state", "hover"], false], 6, 4.5],
        0,
      ],
      "circle-stroke-width": 1,
      "circle-stroke-color": isDark ? "#f5f5f4" : "#382e2e",
    },
  });
}

function applyCounts(map: MapLibreMap, rows: CountryDiversityRow[]) {
  map.removeFeatureState({ source: SOURCE_ID });
  for (const row of rows) {
    map.setFeatureState(
      { source: SOURCE_ID, id: row.countryCode },
      { species: row.speciesCount },
    );
  }
}

function popupContent(
  row: CountryDiversityRow | undefined,
  name: string,
  withLink: boolean,
): HTMLElement {
  const root = document.createElement("div");
  root.className = "text-sm leading-snug";
  const title = document.createElement("div");
  title.className = "font-semibold";
  title.textContent = row?.countryName ?? name;
  root.appendChild(title);
  const detail = document.createElement("div");
  if (row) {
    const imputed =
      row.imputedImageCount > 0
        ? ` (${row.imputedImageCount.toLocaleString("en-US")} imputed)`
        : "";
    detail.textContent = `${row.speciesCount.toLocaleString("en-US")} species · ${row.imageCount.toLocaleString("en-US")} images${imputed}`;
  } else {
    detail.textContent = "No validated records";
  }
  root.appendChild(detail);
  if (row && withLink) {
    const link = document.createElement("a");
    link.href = countryHref(row.countryCode);
    link.className = "mt-1 inline-block text-pacific-blue-600 underline";
    link.textContent = "View species →";
    root.appendChild(link);
  }
  return root;
}

export default function CountryDiversityMap({
  countries,
  className,
}: {
  countries: CountryDiversityRow[];
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const router = useRouter();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const themeRef = useRef<boolean | null>(null);

  // Read by the map's event handlers, which are bound once.
  const rowsRef = useRef(countries);
  const routerRef = useRef(router);
  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  // Create the map once; the theme and the data are applied in place below.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;
    const initialDark = document.documentElement.classList.contains("dark");
    themeRef.current = initialDark;

    configureMapLibreWorker();

    loadLightBasemapStyle(initialDark)
      .catch(
        // No basemap is still a usable map: the countries carry the data.
        (): StyleSpecification => ({
          version: 8,
          sources: {},
          layers: [
            {
              id: "background",
              type: "background",
              paint: {
                "background-color": initialDark ? "#1c1717" : "#f5f5f4",
              },
            },
          ],
        }),
      )
      .then((style) => {
        if (cancelled) return;
        const map = new MapLibreMap({
          container,
          style,
          center: [10, 20],
          zoom: 1,
          maxZoom: MAX_ZOOM,
          renderWorldCopies: false,
          dragRotate: false,
          pitchWithRotate: false,
          fadeDuration: 0,
          // Few zoom levels, few tiles: a small cache is plenty.
          maxTileCacheSize: 64,
          // Scroll-zoom would hijack page scrolling on the landing page.
          scrollZoom: false,
          attributionControl: {
            compact: true,
            customAttribution: getBasemapAttribution(),
          },
        });
        mapRef.current = map;
        map.touchZoomRotate.disableRotation();
        map.addControl(
          new NavigationControl({ showCompass: false }),
          "top-right",
        );
        addProjectionToggle(map);

        const popup = new Popup({
          closeButton: false,
          closeOnClick: false,
          offset: 8,
          maxWidth: "260px",
        });
        const noHover = window.matchMedia("(hover: none)").matches;
        let hovered: string | null = null;

        const setHover = (code: string | null) => {
          if (hovered === code) return;
          if (hovered) {
            map.setFeatureState(
              { source: SOURCE_ID, id: hovered },
              { hover: false },
            );
          }
          hovered = code;
          if (code) {
            map.setFeatureState(
              { source: SOURCE_ID, id: code },
              { hover: true },
            );
          }
        };

        const rowFor = (code: string) =>
          rowsRef.current.find((row) => row.countryCode === code);

        const onMove = (event: MapLayerMouseEvent) => {
          const code = event.features?.[0]?.properties?.code as
            string | undefined;
          if (!code) return;
          map.getCanvas().style.cursor = rowFor(code) ? "pointer" : "";
          setHover(code);
          popup
            .setLngLat(event.lngLat)
            .setDOMContent(popupContent(rowFor(code), code, false))
            .addTo(map);
        };
        const onLeave = () => {
          map.getCanvas().style.cursor = "";
          setHover(null);
          popup.remove();
        };
        const onClick = (event: MapLayerMouseEvent) => {
          const code = event.features?.[0]?.properties?.code as
            string | undefined;
          const row = code ? rowFor(code) : undefined;
          if (!code) return;
          if (noHover) {
            // A touch screen has no hover: the first tap shows the numbers,
            // and the popup carries the link onward.
            setHover(code);
            popup
              .setLngLat(event.lngLat)
              .setDOMContent(popupContent(row, code, true))
              .addTo(map);
            return;
          }
          if (row) routerRef.current.push(countryHref(row.countryCode));
        };

        for (const layer of [FILL_LAYER, MARKER_LAYER]) {
          if (!noHover) {
            map.on("mousemove", layer, onMove);
            map.on("mouseleave", layer, onLeave);
          }
          map.on("click", layer, onClick);
        }

        // `style.load` fires on the first load and after every setStyle(),
        // which drops custom sources, layers and feature state.
        map.on("style.load", () => {
          const dark = themeRef.current ?? false;
          addCountryLayers(map, speciesScale(rowsRef.current, dark), dark);
          applyCounts(map, rowsRef.current);
          hovered = null;
        });

        // Open on the whole world, then stop the reader zooming out past it.
        map.once("load", () => {
          map.fitBounds(WORLD, { animate: false, padding: 4 });
          map.setMinZoom(map.getZoom());
        });

        resizeObserver = new ResizeObserver(() => map.resize());
        resizeObserver.observe(container);
      });

    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // New data: recolor in place.
  useEffect(() => {
    rowsRef.current = countries;
    const map = mapRef.current;
    if (!map?.getLayer(FILL_LAYER)) return;
    const color = colorExpression(
      speciesScale(countries, themeRef.current ?? false),
    );
    map.setPaintProperty(FILL_LAYER, "fill-color", color);
    map.setPaintProperty(MARKER_LAYER, "circle-color", color);
    applyCounts(map, countries);
  }, [countries]);

  // Theme swap: a new basemap, then `style.load` re-adds the countries.
  useEffect(() => {
    if (!resolvedTheme || themeRef.current === isDark) return;
    themeRef.current = isDark;
    let cancelled = false;
    loadLightBasemapStyle(isDark)
      .then((style) => {
        const map = mapRef.current;
        if (!cancelled && map) {
          map.setStyle(style, { diff: false, ...keepProjection(map) });
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [isDark, resolvedTheme]);

  return <div ref={containerRef} className={className} />;
}
