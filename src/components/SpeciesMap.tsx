'use client';

import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { useMemo } from 'react';

// --- Remove Icon Imports --- 
/*
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
*/

interface Occurrence {
  key: string | number;
  decimalLatitude: number;
  decimalLongitude: number;
  // Add other fields you might fetch from GBIF later, e.g., eventDate, basisOfRecord
}

interface SpeciesMapProps {
  occurrences?: Occurrence[]; // Make occurrences optional
}

const SpeciesMap: React.FC<SpeciesMapProps> = ({ occurrences = [] }) => {

  // --- Create Icon Instance using Static Paths ---
  const customIcon = useMemo(() => {
    // console.log('Creating customIcon with static paths'); // Optional logging
    return L.icon({
      iconUrl: '/leaflet/images/marker-icon.png', // Path relative to public folder
      iconRetinaUrl: '/leaflet/images/marker-icon-2x.png', // Path relative to public folder
      shadowUrl: '/leaflet/images/marker-shadow.png', // Path relative to public folder
      iconSize: [25, 41],
      iconAnchor: [12, 41],
      popupAnchor: [1, -34],
      shadowSize: [41, 41]
    });
  }, []); // Empty dependency array ensures it's created only once
  // --- End Icon Instance Creation ---

  // Prevent server-side rendering for MapContainer
  if (typeof window === 'undefined') {
    return <div className="aspect-video bg-gray-200 dark:bg-gray-700 rounded flex items-center justify-center"><span className="text-gray-500">Map loading...</span></div>; // Show placeholder during SSR
  }

  // Calculate center and zoom based on occurrences later
  // For now, keep default center/zoom but adjust slightly if there are occurrences
  const mapCenter: L.LatLngExpression = occurrences.length > 0 
                                        ? [occurrences[0].decimalLatitude, occurrences[0].decimalLongitude] 
                                        : [20, 0]; // Center on first point if available, else default
  const mapZoom = occurrences.length > 0 ? 4 : 2; // Slightly more zoomed in if data exists

  return (
    <MapContainer 
      center={mapCenter} 
      zoom={mapZoom} 
      scrollWheelZoom={true} 
      style={{ height: '400px', width: '100%', borderRadius: '8px' }} 
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &amp; GBIF'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      
      {/* Map over occurrences to add Markers */}
      {occurrences.map((occ, index) => {
        // --- Add Logging Here ---
        console.log(`Rendering Marker ${index}:`, occ);
        // Check if coordinates are valid numbers just before rendering
        if (typeof occ.decimalLatitude !== 'number' || typeof occ.decimalLongitude !== 'number' || isNaN(occ.decimalLatitude) || isNaN(occ.decimalLongitude)) {
          console.error(`Invalid coordinates for occurrence key ${occ.key}:`, occ);
          return null; // Skip rendering this marker if coordinates are invalid
        }
        // --- End Logging --- 

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