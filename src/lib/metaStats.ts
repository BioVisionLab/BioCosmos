import { API_HOST } from "@/lib/config";

export interface TaxonStats {
    gbifEntries: number;
    lepTraitsEntries: number;
    imageEntries: number;
    familyCount: number;
    speciesCount: number;
    sourceDbCount: Record<string, number> | null;
}

async function fetchTaxonStats(): Promise<TaxonStats | null> {
    try {
        const response = await fetch(`${API_HOST}/stats/taxon`, {
            next: { revalidate: 18000 }, // Cache for 5 hours
        });
        if (!response.ok) return null;
        return await response.json();
    } catch {
        return null;
    }
}

export { fetchTaxonStats };