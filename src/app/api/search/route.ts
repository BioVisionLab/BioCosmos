import { NextResponse } from 'next/server';
import { getSpeciesData, SpeciesData } from '@/lib/speciesData';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get('q');

  if (!query) {
    return NextResponse.json({ error: 'Query parameter \'q\' is required' }, { status: 400 });
  }

  try {
    const allSpecies = await getSpeciesData(); // Fetch all species
    const lowerCaseQuery = query.toLowerCase();

    const filteredSpecies = allSpecies.filter(species => 
      species.name.toLowerCase().includes(lowerCaseQuery) || 
      species.commonName.toLowerCase().includes(lowerCaseQuery)
      // Add more fields to search here if needed (e.g., description)
    );

    return NextResponse.json(filteredSpecies);
  } catch (error) {
    console.error("Search API error:", error);
    return NextResponse.json({ error: 'Failed to fetch species data' }, { status: 500 });
  }
} 