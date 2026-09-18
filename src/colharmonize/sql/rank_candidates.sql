CREATE TABLE ranked_candidates AS
WITH candidate_counts AS (
    SELECT input_taxon_key, count(*)::INTEGER AS candidate_count
    FROM candidate_evidence
    GROUP BY input_taxon_key
), classified AS (
    SELECT evidence.*,
        counts.candidate_count,
        CASE
            WHEN strongest_method = 'FAMILY_EPITHET' AND candidate_count = 1
            THEN 'UNIQUE_FAMILY_EPITHET'
            ELSE strongest_method
        END AS candidate_method,
        CASE
            WHEN strongest_method = 'FAMILY_EPITHET' AND candidate_count = 1 THEN 4
            ELSE method_tier
        END AS effective_tier
    FROM candidate_evidence evidence
    JOIN candidate_counts counts USING (input_taxon_key)
), scored AS (
    SELECT *,
        CASE candidate_method
            WHEN 'EXACT_ACCEPTED' THEN 7000
            WHEN 'EXACT_SYNONYM' THEN 6000
            WHEN 'EXACT_CANONICAL' THEN 5000
            WHEN 'UNIQUE_FAMILY_EPITHET' THEN 4000
            WHEN 'SPELLING_GENUS' THEN 3000
            WHEN 'SPELLING_EPITHET' THEN 2000
            WHEN 'FUZZY_TYPO' THEN 1000
            ELSE 500
        END
        + family_exact * 300
        + rank_exact * 100
        + authorship_exact * 200
        + round(genus_similarity * 100)::INTEGER
        + round(epithet_similarity * 100)::INTEGER
        - 25 * (genus_distance + epithet_distance) AS match_score
    FROM classified
), tier_stats AS (
    SELECT input_taxon_key, min(effective_tier) AS best_tier
    FROM scored GROUP BY input_taxon_key
), enriched AS (
    SELECT scored.*,
        count(*) FILTER (WHERE scored.effective_tier = tier_stats.best_tier)
            OVER (PARTITION BY scored.input_taxon_key) AS best_tier_count
    FROM scored
    JOIN tier_stats USING (input_taxon_key)
)
SELECT *,
    row_number() OVER (
        PARTITION BY input_taxon_key
        ORDER BY effective_tier, match_score DESC, accepted_id
    )::INTEGER AS candidate_rank,
    lead(accepted_name) OVER (
        PARTITION BY input_taxon_key
        ORDER BY effective_tier, match_score DESC, accepted_id
    ) AS runner_up_name,
    lead(match_score) OVER (
        PARTITION BY input_taxon_key
        ORDER BY effective_tier, match_score DESC, accepted_id
    ) AS runner_up_score
FROM enriched;
