import { API_HOST } from "@/lib/config";

export interface TaxonStats {
    gbifEntries: number;
    lepTraitsEntries: number;
    imageEntries: number;
    familyCount: number;
    speciesCount: number;
    sourceDbCount: Record<string, number> | null;
    entriesByFamily: Record<string, number> | null;
    topTenSpecies: Record<string, number> | null;
}

/** Five-number summary of one embedding model's component values. */
export interface EmbeddingSummary {
    embeddingModel: string;
    dimensions: number;
    imageCount: number;
    sampleSize: number;
    minimum: number;
    q1: number;
    median: number;
    q3: number;
    maximum: number;
    lowerWhisker: number;
    upperWhisker: number;
    mean: number;
    stdDev: number;
}

export interface EmbeddingStats {
    distributions: EmbeddingSummary[];
}

async function fetchTaxonStats(): Promise<TaxonStats | null> {
    try {
        const response = await fetch(`${API_HOST}/stats/taxon`, {
            // next: { revalidate: 18000 }, // Cache for 5 hours
        });
        if (!response.ok) return null;
        return await response.json();
    } catch {
        return null;
    }
}

/**
 * Fetch CLIP and UNICOM embedding value distributions.
 *
 * Called from the client, so it goes through the Next route handler rather
 * than hitting API_HOST directly.
 */
async function fetchEmbeddingStats(): Promise<EmbeddingStats | null> {
    try {
        const response = await fetch("/api/stats/embeddings");
        if (!response.ok) return null;
        return await response.json();
    } catch {
        return null;
    }
}

export { fetchTaxonStats, fetchEmbeddingStats };
