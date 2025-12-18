// Render Species Map based on GBIF occurrences

import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { useEffect, useMemo } from "react";
import { getTileLayerAttributionUrl, getTileLayerUrl } from "@/lib/map";
import { Occurrence } from "@/lib/map";

interface SpeciesMapProps {
  occurrences?: Occurrence[]; // Make occurrences optional
}

function MapRecenter({
  center,
  zoom,
}: {
  center: L.LatLngExpression;
  zoom: number;
}) {
  const map = useMap();

  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);

  return null;
}

const SpeciesMap: React.FC<SpeciesMapProps> = ({ occurrences = [] }) => {
  const customIcon = useMemo(() => {
    const size = 8;
    const html = `<div style="
      width:${size}px;
      height:${size}px;
      background:#009688;
      opacity:0.8;
      border-radius:50%;
      border:2px solid #009688;
    "></div>`;

    return L.divIcon({
      html,
      className: "",
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      popupAnchor: [0, -size / 2],
    });
  }, []);

  // Calculate center and zoom based on occurrences later
  // For now, keep default center/zoom but adjust slightly if there are occurrences
  const mapCenter: L.LatLngExpression =
    occurrences.length > 0
      ? [occurrences[0].decimalLatitude, occurrences[0].decimalLongitude]
      : [20, 0]; // Center on first point if available, else default
  const mapZoom = occurrences.length > 0 ? 4 : 2; // Slightly more zoomed in if data exists

  return (
    <MapContainer
      center={mapCenter}
      zoom={mapZoom}
      maxZoom={18}
      minZoom={2}
      scrollWheelZoom={true}
      style={{ height: "400px", width: "100%", borderRadius: "12px" }}
    >
      <TileLayer
        attribution={getTileLayerAttributionUrl()}
        url={getTileLayerUrl()}
      />

      {/* Map over occurrences to add Markers */}
      {occurrences.map((occ, index) => {
        // --- Add Logging Here ---
        console.log(`Rendering Marker ${index}:`, occ);
        // Check if coordinates are valid numbers just before rendering
        if (
          typeof occ.decimalLatitude !== "number" ||
          typeof occ.decimalLongitude !== "number" ||
          isNaN(occ.decimalLatitude) ||
          isNaN(occ.decimalLongitude)
        ) {
          console.error(
            `Invalid coordinates for occurrence key ${occ.key}:`,
            occ
          );
          return null; // Skip rendering this marker if coordinates are invalid
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
              {/* Add more details here later if fetched */}
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
};

export default SpeciesMap;
