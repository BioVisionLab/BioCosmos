"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MapLibreMap, NavigationControl, Popup } from "maplibre-gl";
import type { GeoJSONSource, MapLayerMouseEvent } from "maplibre-gl";
import { useTheme } from "next-themes";
import "maplibre-gl/dist/maplibre-gl.css";
import { getBasemapAttribution, getBasemapStyleUrl } from "@/lib/map";
import { configureMapLibreWorker } from "@/lib/maplibreWorker";

const SOURCE_ID = "points";
const LAYER_ID = "points-circles";

export interface MapPoint {
  id: string | number;
  lat: number;
  lon: number;
  color: string;
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

  const addPointsLayer = useCallback((map: MapLibreMap) => {
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
          "circle-radius": circleRadiusRef.current,
          "circle-color": ["get", "color"],
          "circle-opacity": 0.85,
          "circle-stroke-width": 1,
          "circle-stroke-color": "rgba(255,255,255,0.7)",
        },
      });
    }
  }, []);

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
      minZoom,
      maxZoom,
      attributionControl: { compact: true, customAttribution: getBasemapAttribution() },
    });
    mapRef.current = map;

    map.addControl(
      new NavigationControl({ showCompass: false }),
      "top-right",
    );

    const popup = new Popup({
      closeButton: interaction === "click",
      closeOnClick: interaction === "click",
      offset: circleRadiusRef.current + 2,
      maxWidth: "none",
      // A hover popup under the cursor would trigger mouseleave on the layer
      // and flicker itself in and out.
      className: interaction === "hover" ? "pointer-events-none" : undefined,
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

    popup.on("close", () => {
      activePointIdRef.current = null;
      setActivePoint(null);
    });

    // The specimens tab hides and re-shows the map; resizing on its own keeps
    // the canvas from rendering at a stale size.
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(container);

    return () => {
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
    map.setStyle(styleUrl);
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
    }
  }, [activePoint]);

  useEffect(() => {
    const map = mapRef.current;
    if (map?.getLayer(LAYER_ID)) {
      map.setPaintProperty(LAYER_ID, "circle-radius", circleRadius);
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
