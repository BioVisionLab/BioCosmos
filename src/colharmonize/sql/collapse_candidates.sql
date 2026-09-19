CREATE TABLE candidate_evidence AS
WITH aggregated AS (
    SELECT
        input_taxon_key,
        accepted_id,
        min(accepted_name) AS accepted_name,
        min(accepted_authorship) AS accepted_authorship,
        min(accepted_genus) AS accepted_genus,
        min(accepted_epithet) AS accepted_epithet,
        min(accepted_family) AS accepted_family,
        min(accepted_status) AS accepted_status,
        min(accepted_rank) AS accepted_rank,
        min(match_stage) AS match_stage,
        string_agg(DISTINCT generation_method, ',' ORDER BY generation_method)
            AS generation_methods,
        max(family_exact) AS family_exact,
        max(rank_exact) AS rank_exact,
        max(authorship_exact) AS authorship_exact,
        min(genus_distance) AS genus_distance,
        min(epithet_distance) AS epithet_distance,
        max(genus_similarity) AS genus_similarity,
        max(epithet_similarity) AS epithet_similarity
    FROM raw_candidates
    GROUP BY input_taxon_key, accepted_id
), strongest AS (
    SELECT * EXCLUDE (candidate_order)
    FROM (
        SELECT
            input_taxon_key,
            accepted_id,
            generation_method AS strongest_method,
            tier AS method_tier,
            matched_usage_id,
            matched_usage_name,
            matched_usage_status,
            row_number() OVER (
                PARTITION BY input_taxon_key, accepted_id
                ORDER BY tier, generation_method, matched_usage_id
            ) AS candidate_order
        FROM raw_candidates
    )
    WHERE candidate_order = 1
)
SELECT aggregated.*, strongest.strongest_method, strongest.method_tier,
    strongest.matched_usage_id, strongest.matched_usage_name,
    strongest.matched_usage_status
FROM aggregated
JOIN strongest USING (input_taxon_key, accepted_id);
