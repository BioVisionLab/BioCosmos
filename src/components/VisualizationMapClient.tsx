"use client";
import React, { useEffect, useRef } from "react";
import { MapLibreMap, NavigationControl } from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { configureMapLibreWorker } from "@/lib/maplibreWorker";

const TILE_URL = "/dataset-tiles/{z}/{x}/{y}.png";
// create_tiles.py also writes @2x variants alongside the standard tiles.
const TILE_URL_HQ = "/dataset-tiles/{z}/{x}/{y}@2x.png";
// Deepest level create_tiles.py output that is worth requesting.
const MAX_SOURCE_ZOOM = 7;
// MapLibre sizes zoom levels against 512px tiles, so a 256px raster source
// resolves one level deeper than the map zoom: map zoom 6 pulls tile z7.
const MAX_MAP_ZOOM = MAX_SOURCE_ZOOM - 1;
// The whole tile pyramid covers the Web Mercator world square.
const CANVAS_BOUNDS: [[number, number], [number, number]] = [
  [-180, -85.051129],
  [180, 85.051129],
];

// The tile pyramid is a plain XYZ grid over the unit square (see
// tools/create_tiles.py), so it lines up with the Web Mercator world tile
// scheme without any coordinate translation.
function buildStyle(): StyleSpecification {
  const isRetina =
    typeof window !== "undefined" && window.devicePixelRatio > 1;

  return {
    version: 8,
    sources: {
      dataset: {
        type: "raster",
        tiles: [isRetina ? TILE_URL_HQ : TILE_URL],
        // @2x images are 512px but still cover one 256px tile slot.
        tileSize: 256,
        minzoom: 0,
        maxzoom: MAX_SOURCE_ZOOM,
        scheme: "xyz",
        attribution: "Biocosmos Dataset Visualization",
      },
    },
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": "#000000" },
      },
      { id: "dataset", type: "raster", source: "dataset" },
    ],
  };
}

export default function VisualizationMapClient() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    configureMapLibreWorker();

    const map = new MapLibreMap({
      container,
      style: buildStyle(),
      center: [0, 0],
      zoom: 0,
      maxZoom: MAX_MAP_ZOOM,
      renderWorldCopies: false,
      dragRotate: false,
      pitchWithRotate: false,
      attributionControl: { compact: true },
    });

    map.touchZoomRotate.disableRotation();

    // Open on the whole canvas, then stop the reader zooming back out past it.
    // MapLibre keeps the tile square covering the viewport, so the canvas
    // fills the container and the shorter axis is cropped rather than
    // letterboxed; create_tiles.py pads the embedding by 5% a side, and the
    // rest is reachable by panning.
    map.once("load", () => {
      map.fitBounds(CANVAS_BOUNDS, { animate: false, padding: 8 });
      map.setMinZoom(map.getZoom());
    });

    map.addControl(
      new NavigationControl({ showCompass: false }),
      "top-right",
    );

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      map.remove();
    };
  }, []);

  return (
    <div
      style={{ height: "80vh", width: "100%" }}
      className="bg-black rounded-md overflow-hidden select-none"
    >
      <div ref={containerRef} style={{ height: "100%", width: "100%" }} />
    </div>
  );
}
