"use client";

// Render Species Map based on GBIF occurrences
// Use client
import {
  MapContainer,
  Marker,
  useMap,
  Tooltip,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { useMemo, useEffect, useState } from "react";
import { useTheme } from "next-themes";
import {
  getTileLayerAttributionUrl,
  UmapOccurrence,
} from "@/lib/map";

const DARK_TILE_URL =
  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const LIGHT_TILE_URL =
  "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
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
    let isCancelled = false;
    let timer: number | undefined;

    const syncMapView = () => {
      if (isCancelled) {
        return;
      }

      const container = map.getContainer();
      if (!container || !container.isConnected) {
        return;
      }

      try {
        map.setView(center, zoom, { animate: false });
      } catch {
        return;
      }

      // Delay invalidateSize slightly to avoid gray tiles during tab transitions.
      timer = window.setTimeout(() => {
        if (isCancelled) {
          return;
        }

        const activeContainer = map.getContainer();
        if (!activeContainer || !activeContainer.isConnected) {
          return;
        }

        try {
          map.invalidateSize();
        } catch {
          // Ignore transient errors during rapid mount/unmount cycles.
        }
      }, 100);
    };

    map.whenReady(syncMapView);

    return () => {
      isCancelled = true;
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [center, zoom, map]);

  return null;
}

function SafeTileLayer({
  tileUrl,
  className,
}: {
  tileUrl: string;
  className?: string;
}) {
  const map = useMap();

  useEffect(() => {
    if (!map) {
      return;
    }

    // During Fast Refresh, Leaflet can transiently lose panes.
    const tilePane = map.getPane("tilePane");
    if (!tilePane) {
      return;
    }

    const layer = L.tileLayer(tileUrl, {
      attribution: getTileLayerAttributionUrl(),
      className,
    });

    layer.addTo(map);

    return () => {
      map.removeLayer(layer);
    };
  }, [map, tileUrl, className]);

  return null;
}

export default function UmapClusterDistribution({
  occurrences,
  clusterColors,
}: {
  occurrences: UmapOccurrence[];
  clusterColors: string[];
}): React.ReactElement {
  const [isMounted, setIsMounted] = useState(false);
  const { resolvedTheme } = useTheme();
  const isDarkTheme = resolvedTheme === "dark";
  const tileUrl = isDarkTheme ? DARK_TILE_URL : LIGHT_TILE_URL;

  // Calculate center based on occurrences
  const mapCenter: L.LatLngExpression = useMemo(() => {
    return occurrences.length > 0
      ? [occurrences[0].decimalLatitude, occurrences[0].decimalLongitude]
      : [20, 0];
  }, [occurrences]);

  const mapZoom = occurrences.length > 0 ? 4 : 2;

  useEffect(() => {
    setIsMounted(true);
  }, []);

  if (occurrences.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500 rounded-xl border border-gray-500">
        No geographic distribution data available.
      </div>
    );
  }

  if (!isMounted) {
    return <div style={{ height: "100%", width: "100%", borderRadius: "12px" }} />;
  }

  // Function to create icon for each cluster
  const createClusterIcon = (cluster: number) => {
    const size = 14;
    const fillColor = clusterColors[cluster % clusterColors.length];
    const html = `<div style="
      width:${size}px;
      height:${size}px;
      background:${fillColor};
      border-radius:50%;
      border:1px solid rgba(255,255,255,0.7);
      opacity:0.9;
      box-shadow:0 0 0 1px rgba(8, 15, 33, 0.35);
    "></div>`;

    return L.divIcon({
      html,
      className: "",
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      popupAnchor: [0, -size / 2],
    });
  };

  return (
    <div className={isDarkTheme ? "umap-dark-map" : ""} style={{ height: "100%", width: "100%" }}>
      <MapContainer
        center={mapCenter}
        zoom={mapZoom}
        maxZoom={19}
        minZoom={2}
        scrollWheelZoom={true}
        style={{ height: "100%", width: "100%", borderRadius: "12px" }}
        key="umap-cluster-distribution-map"
      >
        <SafeTileLayer
          tileUrl={tileUrl}
          className={isDarkTheme ? "umap-site-tiles" : undefined}
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
    </div>
  );
}
