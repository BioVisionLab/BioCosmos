"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MapLibreMap, NavigationControl, Popup } from "maplibre-gl";
import type { GeoJSONSource, MapLayerMouseEvent } from "maplibre-gl";
import { useTheme } from "next-themes";
import "maplibre-gl/dist/maplibre-gl.css";
import { getBasemapAttribution, getBasemapStyleUrl } from "@/lib/map";
import { addProjectionToggle, keepProjection } from "@/lib/mapProjection";
import { configureMapLibreWorker } from "@/lib/maplibreWorker";

const SOURCE_ID = "points";
const LAYER_ID = "points-circles";
const UNDERLAY_SOURCE_ID = "underlay";
const UNDERLAY_LAYER_ID = "underlay-raster";

export interface MapPoint {
  id: string | number;
  lat: number;
  lon: number;
  color: string;
  /** Overrides the map-wide `circleRadius` for this point. */
  radius?: number;
  /** Overrides the default white outline for this point. */
  strokeColor?: string;
}

/** A raster tile layer drawn beneath the points, such as a density map. */
export interface RasterUnderlay {
  /** Changing it replaces the layer; the same id leaves it alone. */
  id: string;
  tiles: string[];
  attribution?: string;
  opacity?: number;
  tileSize?: number;
}

interface PointMapProps {
  points: MapPoint[];
  /** Radius of each point in pixels. */
  circleRadius: number;
  /** [longitude, latitude] — MapLibre's order. The camera jumps here when it changes. */
  center: [number, number];
  zoom: number;
  minZoom?: number;
  maxZoom?: number;
  /** Whether the popup opens on click or follows the cursor. */
  interaction: "click" | "hover";
  renderPopup: (point: MapPoint) => React.ReactNode;
  rasterUnderlay?: RasterUnderlay | null;
  /** Extra class on the popup, for a map that styles its own. */
  popupClassName?: string;
  /** Fit the camera to these [[west, south], [east, north]] bounds on load. */
  fitBounds?: [[number, number], [number, number]] | null;
  className?: string;
  style?: React.CSSProperties;
}

function toFeatureCollection(
  points: MapPoint[],
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: points
      .filter(
        (point) =>
          Number.isFinite(point.lat) &&
          Number.isFinite(point.lon) &&
          Math.abs(point.lat) <= 90,
      )
      .map((point) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [point.lon, point.lat] },
        properties: { ...point },
      })),
  };
}

export default function PointMap({
  points,
  circleRadius,
  center,
  zoom,
  minZoom = 2,
  maxZoom = 18,
  interaction,
  renderPopup,
  rasterUnderlay = null,
  popupClassName,
  fitBounds = null,
  className,
  style,
}: PointMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const popupRef = useRef<Popup | null>(null);
  // React renders popup content into this detached node via a portal.
  const popupHostRef = useRef<HTMLDivElement | null>(null);
  const styleUrlRef = useRef<string | null>(null);
  const centerRef = useRef<[number, number] | null>(null);
  const [activePoint, setActivePoint] = useState<MapPoint | null>(null);
  const activePointIdRef = useRef<string | number | null>(null);

  const { resolvedTheme } = useTheme();
  const isDarkTheme = resolvedTheme === "dark";

  const featureCollection = useMemo(
    () => toFeatureCollection(points),
    [points],
  );
  // Keep the latest data in a ref so `style.load` can re-add the layer after a
  // theme swap without re-creating the map.
  const featureCollectionRef = useRef(featureCollection);
  featureCollectionRef.current = featureCollection;

  const circleRadiusRef = useRef(circleRadius);
  circleRadiusRef.current = circleRadius;

  const rasterUnderlayRef = useRef(rasterUnderlay);
  // Synced in an effect declared before the map is created, so it is current
  // by the time `style.load` reads it; effects run in declaration order.
  useEffect(() => {
    rasterUnderlayRef.current = rasterUnderlay;
  }, [rasterUnderlay]);
  const underlayIdRef = useRef<string | null>(null);

  const addUnderlay = useCallback((map: MapLibreMap) => {
    const underlay = rasterUnderlayRef.current;
    if (map.getLayer(UNDERLAY_LAYER_ID)) map.removeLayer(UNDERLAY_LAYER_ID);
    if (map.getSource(UNDERLAY_SOURCE_ID)) map.removeSource(UNDERLAY_SOURCE_ID);
    underlayIdRef.current = underlay?.id ?? null;
    if (!underlay) return;

    map.addSource(UNDERLAY_SOURCE_ID, {
      type: "raster",
      tiles: underlay.tiles,
      tileSize: underlay.tileSize ?? 256,
      attribution: underlay.attribution,
    });
    // Beneath the points whenever they exist, so markers stay clickable.
    map.addLayer(
      {
        id: UNDERLAY_LAYER_ID,
        type: "raster",
        source: UNDERLAY_SOURCE_ID,
        paint: { "raster-opacity": underlay.opacity ?? 0.8 },
      },
      map.getLayer(LAYER_ID) ? LAYER_ID : undefined,
    );
  }, []);

  const addPointsLayer = useCallback(
    (map: MapLibreMap) => {
      addUnderlay(map);
      if (!map.getSource(SOURCE_ID)) {
        map.addSource(SOURCE_ID, {
          type: "geojson",
          data: featureCollectionRef.current,
        });
      }

      if (!map.getLayer(LAYER_ID)) {
        map.addLayer({
          id: LAYER_ID,
          type: "circle",
          source: SOURCE_ID,
          paint: {
            "circle-radius": [
              "coalesce",
              ["get", "radius"],
              circleRadiusRef.current,
            ],
            "circle-color": ["get", "color"],
            "circle-opacity": 0.85,
            "circle-stroke-width": 1,
            "circle-stroke-color": [
              "coalesce",
              ["get", "strokeColor"],
              "rgba(255,255,255,0.7)",
            ],
          },
        });
      }
    },
    [addUnderlay],
  );

  // Create the map once. Theme and data changes are applied in place below.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    configureMapLibreWorker();

    const popupHost = document.createElement("div");
    popupHostRef.current = popupHost;

    const initialStyleUrl = getBasemapStyleUrl(
      document.documentElement.classList.contains("dark"),
    );
    styleUrlRef.current = initialStyleUrl;

    centerRef.current = center;

    const map = new MapLibreMap({
      container,
      style: initialStyleUrl,
      center,
      zoom,
      ...(fitBounds
        ? { bounds: fitBounds, fitBoundsOptions: { padding: 40, maxZoom: 6 } }
        : {}),
      minZoom,
      maxZoom,
      attributionControl: {
        compact: true,
        customAttribution: getBasemapAttribution(),
      },
    });
    mapRef.current = map;

    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    addProjectionToggle(map);

    const popup = new Popup({
      closeButton: interaction === "click",
      closeOnClick: interaction === "click",
      offset: circleRadiusRef.current + 2,
      maxWidth: "none",
      // A hover popup under the cursor would trigger mouseleave on the layer
      // and flicker itself in and out.
      className:
        [interaction === "hover" ? "pointer-events-none" : null, popupClassName]
          .filter(Boolean)
          .join(" ") || undefined,
    });
    popup.setDOMContent(popupHost);
    popupRef.current = popup;

    // `style.load` fires on the initial load and again after every setStyle(),
    // which drops custom sources and layers.
    map.on("style.load", () => addPointsLayer(map));

    const showPopup = (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      if (!feature) {
        return;
      }

      const point = feature.properties as unknown as MapPoint;
      if (activePointIdRef.current === point.id && popup.isOpen()) {
        return;
      }

      activePointIdRef.current = point.id;
      setActivePoint(point);
      popup.setLngLat([point.lon, point.lat]).addTo(map);
    };

    if (interaction === "click") {
      map.on("click", LAYER_ID, showPopup);
      map.on("mouseenter", LAYER_ID, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", LAYER_ID, () => {
        map.getCanvas().style.cursor = "";
      });
    } else {
      map.on("mousemove", LAYER_ID, (event: MapLayerMouseEvent) => {
        map.getCanvas().style.cursor = "pointer";
        showPopup(event);
      });
      map.on("mouseleave", LAYER_ID, () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
        activePointIdRef.current = null;
        setActivePoint(null);
      });
    }

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && popup.isOpen()) popup.remove();
    };
    if (interaction === "click") {
      document.addEventListener("keydown", closeOnEscape);
    }

    popup.on("close", () => {
      activePointIdRef.current = null;
      setActivePoint(null);
    });

    // The specimens tab hides and re-shows the map; resizing on its own keeps
    // the canvas from rendering at a stale size.
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(container);

    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      resizeObserver.disconnect();
      popup.remove();
      map.remove();
      mapRef.current = null;
      popupRef.current = null;
      popupHostRef.current = null;
    };
    // Interaction mode is fixed for a given map; the camera is handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addPointsLayer, interaction]);

  // Swap the underlay when it changes identity. Before the style has loaded,
  // `style.load` adds it from the ref instead.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    if ((rasterUnderlay?.id ?? null) === underlayIdRef.current) return;
    addUnderlay(map);
  }, [rasterUnderlay, addUnderlay]);

  // Push new points without tearing the map down.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;
    if (source) {
      source.setData(featureCollection);
    }
  }, [featureCollection]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !resolvedTheme) {
      return;
    }

    const styleUrl = getBasemapStyleUrl(isDarkTheme);
    if (styleUrl === styleUrlRef.current) {
      return;
    }

    styleUrlRef.current = styleUrl;
    map.setStyle(styleUrl, keepProjection(map));
  }, [isDarkTheme, resolvedTheme]);

  useEffect(() => {
    const map = mapRef.current;
    const previous = centerRef.current;
    if (!map || !previous) {
      return;
    }

    if (previous[0] === center[0] && previous[1] === center[1]) {
      return;
    }

    centerRef.current = center;
    map.jumpTo({ center, zoom });
  }, [center, zoom]);

  // React fills the popup host after MapLibre has already measured it, so
  // re-attach the node to make the popup re-anchor against its real size.
  useEffect(() => {
    const popup = popupRef.current;
    const popupHost = popupHostRef.current;
    if (activePoint && popup?.isOpen() && popupHost) {
      popup.setDOMContent(popupHost);
      // In a small map a popup can be taller than the room beside its point,
      // and the container clips it. Pan just far enough to bring it inside,
      // but only for a click popup: one that follows the cursor would drag
      // the map along with it.
      const map = mapRef.current;
      const container = containerRef.current;
      if (interaction !== "click" || !map || !container) return;
      // Measured a frame later, once MapLibre has re-laid the popup out
      // around its new content.
      const frame = requestAnimationFrame(() => {
        const element = popup.getElement();
        if (!element || !popup.isOpen()) return;
        const margin = 8;
        // The attribution strip sits over the bottom edge.
        const bottomMargin = 44;
        const box = element.getBoundingClientRect();
        const view = container.getBoundingClientRect();
        const dx =
          box.left < view.left + margin
            ? box.left - view.left - margin
            : box.right > view.right - margin
              ? box.right - view.right + margin
              : 0;
        const dy =
          box.top < view.top + margin
            ? box.top - view.top - margin
            : box.bottom > view.bottom - bottomMargin
              ? box.bottom - view.bottom + bottomMargin
              : 0;
        if (dx !== 0 || dy !== 0) map.panBy([dx, dy], { duration: 250 });
      });
      return () => cancelAnimationFrame(frame);
    }
  }, [activePoint, interaction]);

  useEffect(() => {
    const map = mapRef.current;
    if (map?.getLayer(LAYER_ID)) {
      map.setPaintProperty(LAYER_ID, "circle-radius", [
        "coalesce",
        ["get", "radius"],
        circleRadius,
      ]);
    }
  }, [circleRadius]);

  return (
    <div ref={containerRef} className={className} style={style}>
      {activePoint && popupHostRef.current
        ? createPortal(renderPopup(activePoint), popupHostRef.current)
        : null}
    </div>
  );
}
