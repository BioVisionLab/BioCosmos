// Remove 'use client'; directive
// 'use client'; 

// Remove client-side imports
// import React, { useState, useEffect } from 'react';
// We still need Image and Link if they are used *within* the server component part, but they aren't here.
// We only need getSpeciesData import here.
import { getSpeciesData, getGenusList, GenusSummary } from '@/lib/speciesData';
// Import the client component
import HomeClient from '@/components/HomeClient';

// Remove commented-out getSpeciesData function
/*
async function getSpeciesData() { ... }
*/

// Remove Species interface definition (it's needed in HomeClient.tsx)
/*
interface Species {
  name: string;
  imageUrl: string;
  originalFolderName: string;
}
*/

// This remains the default export, fetches data, and renders the client component
export default async function HomePage() { 
  // Fetch the list of genera instead of all species
  const initialGenusList = await getGenusList("Nymphalidae"); // Specify the family
  
  // Pass the fetched genus data to the client component
  // Ensure the prop name matches what HomeClient will expect (e.g., initialGenusList)
  return <HomeClient initialGenusList={initialGenusList} />;
}

// REMOVE the HomeClient function definition from this file
/*
function HomeClient({ initialSpeciesList }: { initialSpeciesList: Species[] }) {
  // ... component code ...
}
*/
