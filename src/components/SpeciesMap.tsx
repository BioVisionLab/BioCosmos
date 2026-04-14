"use client";

import { useEffect, useRef, useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import { useTheme } from "next-themes";
import L from "leaflet";

const DARK_TILE_URL =
  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const LIGHT_TILE_URL =
  "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

import { Occurrence } from "@/lib/map";

interface SpeciesMapProps {
  occurrences?: Occurrence[];
}


// Defined outside SpeciesMap so React never treats it as a new component type
// on re-render. Imperatively calls .setUrl() on theme change — no map remount.
interface ThemeTileLayerProps {
  tileUrl: string;
  className?: string;
}

const ThemeTileLayer = ({ tileUrl, className }: ThemeTileLayerProps) => {
  const layerRef = useRef<L.TileLayer | null>(null);

  useEffect(() => {
    if (layerRef.current) {
      layerRef.current.setUrl(tileUrl);
    }
  }, [tileUrl]);

  return (
    <TileLayer
      ref={layerRef}
      url={tileUrl}
      className={className}
    />
  );
};

const SpeciesMap: React.FC<SpeciesMapProps> = ({ occurrences = [] }) => {
  const [isMounted, setIsMounted] = useState(false);
  const { resolvedTheme } = useTheme();
  const isDarkTheme = resolvedTheme === "dark";
  const tileUrl = isDarkTheme ? DARK_TILE_URL : LIGHT_TILE_URL;

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const customIcon = useMemo(() => {
    const size = 8;
    const html = `<div style="
      width:${size}px;
      height:${size}px;
      background:#10b981;
      opacity:0.8;
      border-radius:50%;
      border:1px solid rgba(255,255,255,0.7);
      box-shadow:0 0 0 1px rgba(8, 15, 33, 0.35);
    "></div>`;

    return L.divIcon({
      html,
      className: "",
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      popupAnchor: [0, -size / 2],
    });
  }, []);

  const mapCenter: L.LatLngExpression =
    occurrences.length > 0
      ? [occurrences[0].decimalLatitude, occurrences[0].decimalLongitude]
      : [20, 0];
  const mapZoom = occurrences.length > 0 ? 4 : 2;

  if (!isMounted) {
    return (
      <div style={{ height: "400px", width: "100%", borderRadius: "12px" }} />
    );
  }

  return (
    <div
      className={isDarkTheme ? "umap-dark-map" : ""}
      style={{ height: "400px", width: "100%" }}
    >
      <MapContainer
        center={mapCenter}
        zoom={mapZoom}
        maxZoom={18}
        minZoom={2}
        scrollWheelZoom={true}
        style={{ height: "400px", width: "100%", borderRadius: "12px" }}
      >
        <ThemeTileLayer
          tileUrl={tileUrl}
          className={isDarkTheme ? "umap-site-tiles" : undefined}
        />

        {occurrences.map((occ, index) => {
          console.log(`Rendering Marker ${index}:`, occ);

          if (
            typeof occ.decimalLatitude !== "number" ||
            typeof occ.decimalLongitude !== "number" ||
            isNaN(occ.decimalLatitude) ||
            isNaN(occ.decimalLongitude)
          ) {
            console.error(
              `Invalid coordinates for occurrence key ${occ.key}:`,
              occ,
            );
            return null;
          }

          return (
            <Marker
              key={occ.key}
              position={[occ.decimalLatitude, occ.decimalLongitude]}
              icon={customIcon}
            >
              <Popup>
                Occurrence Record <br />
                Lat: {occ.decimalLatitude.toFixed(4)} <br />
                Lon: {occ.decimalLongitude.toFixed(4)}
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
};

export default SpeciesMap;