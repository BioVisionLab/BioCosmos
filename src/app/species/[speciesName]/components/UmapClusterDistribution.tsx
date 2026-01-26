// Render Species Map based on GBIF occurrences
// Use client
import {
  MapContainer,
  TileLayer,
  Marker,
  useMap,
  Tooltip,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { useMemo, useEffect, useState } from "react";
import {
  getTileLayerAttributionUrl,
  getTileLayerUrl,
  UmapOccurrence,
} from "@/lib/map";
import { fetchThumbnailById } from "@/lib/images";
import { ImageLoading } from "@/components/Loadings";
import Image from "next/image";
import { toTitleCase } from "@/lib/textUtils";

const MAP_IMAGE_SIZE = 120;

function MapImage({ imgId }: { imgId: string }) {
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchImageUrl = async () => {
      try {
        const url = await fetchThumbnailById(imgId);
        setImgUrl(url);
      } catch (err) {
        console.error("Error fetching cluster image:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchImageUrl();
  }, [imgId]);

  if (!imgUrl) {
    return <ImageLoading size={MAP_IMAGE_SIZE} />;
  }

  if (loading) {
    return <ImageLoading size={MAP_IMAGE_SIZE} />;
  }

  return (
    <div className="flex items-center justify-center">
      <Image
        src={imgUrl}
        alt={`Cluster ${imgId}`}
        width={MAP_IMAGE_SIZE}
        height={MAP_IMAGE_SIZE}
      />
    </div>
  );
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
    // 1. Handle coordinates/zoom updates
    map.setView(center, zoom);

    // 2. Fix the "Tab Switch" gray map issue
    // We use a tiny timeout to ensure the tab's transition/animation
    // has finished and the container actually has its new width/height.
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 100);

    return () => clearTimeout(timer);
  }, [center, zoom, map]);

  return null;
}

export default function UmapClusterDistribution({
  occurrences,
  clusterColors,
}: {
  occurrences: UmapOccurrence[];
  clusterColors: string[];
}): React.ReactElement {
  if (occurrences.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500 rounded-xl border border-gray-500">
        No geographic distribution data available.
      </div>
    );
  }

  // Function to create icon for each cluster
  const createClusterIcon = (cluster: number) => {
    const size = 14;
    const color = clusterColors[cluster % clusterColors.length];
    const html = `<div style="
      width:${size}px;
      height:${size}px;
      background:${color};
      border-radius:50%;
      border:2px solid ${color};
    "></div>`;

    return L.divIcon({
      html,
      className: "",
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      popupAnchor: [0, -size / 2],
    });
  };

  // Calculate center based on occurrences
  const mapCenter: L.LatLngExpression = useMemo(() => {
    return occurrences.length > 0
      ? [occurrences[0].decimalLatitude, occurrences[0].decimalLongitude]
      : [20, 0];
  }, [occurrences]);

  const mapZoom = occurrences.length > 0 ? 4 : 2;

  return (
    <MapContainer
      center={mapCenter}
      zoom={mapZoom}
      maxZoom={19}
      minZoom={2}
      scrollWheelZoom={true}
      style={{ height: "100%", width: "100%", borderRadius: "12px" }}
    >
      <TileLayer
        attribution={getTileLayerAttributionUrl()}
        url={getTileLayerUrl()}
      />
      {/* Map over occurrences to add Markers */}
      <MapRecenter center={mapCenter} zoom={mapZoom} />
      {occurrences.map((occ, index) => {
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
          return null;
        }

        return (
          <Marker
            key={occ.key}
            position={[occ.decimalLatitude, occ.decimalLongitude]}
            icon={createClusterIcon(occ.cluster)}
            opacity={0.8}
          >
            <Tooltip>
              <div>
                <MapImage imgId={occ.key.toString()} />
                <p className="font-semibold">Cluster {occ.cluster}</p>
                <p>{toTitleCase(occ.classDv)}</p>
                <p>
                  Lat: {occ.decimalLatitude.toFixed(4)} <br />
                  Lon: {occ.decimalLongitude.toFixed(4)}
                </p>
              </div>
            </Tooltip>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
