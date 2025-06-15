import { NextResponse } from 'next/server';
import { getSpeciesData, SpeciesData } from '@/lib/speciesData';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  // Accept multiple IDs via comma-separated string or single ID
  const idsParam = searchParams.get('ids');
  const idParam = searchParams.get('id');

  let idsToFetch: string[] = [];

  if (idsParam) {
    idsToFetch = idsParam.split(',').map(id => decodeURIComponent(id.trim())).filter(id => id);
  } else if (idParam) {
    idsToFetch = [decodeURIComponent(idParam.trim())];
  }

  if (idsToFetch.length === 0) {
    return NextResponse.json({ error: 'Query parameter \'id\' or \'ids\' is required' }, { status: 400 });
  }

  console.log(`API: Fetching species details for IDs: ${idsToFetch.join(', ')}`);

  try {
    // Fetch details for each species ID concurrently
    const speciesPromises = idsToFetch.map(id => getSpeciesData(id));
    const speciesDetails = await Promise.all(speciesPromises);

    // Filter out null results (species not found)
    const validSpeciesData = speciesDetails.filter((species): species is SpeciesData => species !== null);

    console.log(`API: Returning data for ${validSpeciesData.length} species.`);

    // If only one ID was requested originally, return single object or null 
    // (optional, depends on how frontend wants to handle it - simpler to always return array)
    // if (idParam && validSpeciesData.length <= 1) {
    //   return NextResponse.json(validSpeciesData[0] || null);
    // }

    // Return array of species data
    return NextResponse.json(validSpeciesData);

  } catch (error) {
    console.error(`Error fetching species details for IDs [${idsToFetch.join(', ')}]:`, error);
    const errorMessage = error instanceof Error ? error.message : 'An unknown error occurred';
    return NextResponse.json({ error: `Failed to fetch species details: ${errorMessage}` }, { status: 500 });
  }
} 