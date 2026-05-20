"use client";
import React, { useEffect, useRef } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const TILE_URL = "/dataset-tiles/{z}/{x}/{y}.png";
const MAX_ZOOM = 7;
const MAP_DEFAULT_ZOOM = 3;
const imageWidth = 250; // replace with your canvas width
const imageHeight = -250; // replace with your canvas height
const canvasCenter: [number, number] = [imageHeight / 2, imageWidth / 2]; // e.g., [500, 500]
const bounds: L.LatLngBoundsExpression = [
  [0, 0] as [number, number],
  [imageHeight, imageWidth] as [number, number],
];

export default function VisualizationMapClient() {
  const mapRef = useRef<L.Map>(null);

  useEffect(() => {
    if (mapRef.current) {
      setTimeout(() => mapRef.current!.fitBounds(bounds), 0);
    }
  }, []);

  return (
    <div
      style={{ height: "80vh", width: "100%" }}
      className="bg-black rounded-md overflow-hidden"
    >
      <MapContainer
        ref={mapRef}
        center={canvasCenter}
        zoom={MAP_DEFAULT_ZOOM}
        minZoom={3}
        maxZoom={7}
        scrollWheelZoom={true}
        style={{ height: "100%", width: "100%" }}
        crs={L.CRS.Simple}
        className="select-none"
      >
        <TileLayer
          url={TILE_URL}
          attribution="Biocosmos Dataset Visualization"
          minZoom={0}
          maxZoom={MAX_ZOOM}
          noWrap={true}
          detectRetina={true}
          keepBuffer={10}
        />
      </MapContainer>
    </div>
  );
}
