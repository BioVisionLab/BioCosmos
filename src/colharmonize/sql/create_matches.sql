CREATE TABLE taxonomy_matches AS
WITH alternatives AS (
    SELECT input_taxon_key,
        string_agg(accepted_name, '; ' ORDER BY candidate_rank) AS alternative_matches
    FROM ranked_candidates
    WHERE candidate_rank BETWEEN 2 AND 4
    GROUP BY input_taxon_key
), selected AS (
    SELECT *,
        CASE
            WHEN match_stage = 'genus' THEN
                CASE WHEN candidate_count = 1 THEN 'MATCHED' ELSE 'AMBIGUOUS' END
            WHEN candidate_method IN ('EXACT_ACCEPTED', 'EXACT_SYNONYM', 'EXACT_CANONICAL')
                 AND best_tier_count = 1 THEN 'MATCHED'
            WHEN candidate_method = 'UNIQUE_FAMILY_EPITHET' THEN 'MATCHED'
            WHEN candidate_method IN ('SPELLING_GENUS', 'SPELLING_EPITHET', 'FUZZY_TYPO')
                 AND (candidate_count = 1
                      OR match_score - runner_up_score >= :min_score_margin)
            THEN 'MATCHED'
            ELSE 'AMBIGUOUS'
        END AS candidate_status
    FROM ranked_candidates
    WHERE candidate_rank = 1
)
SELECT
    inputs.input_taxon_key,
    inputs.original_scientific_name,
    inputs.original_genus,
    inputs.original_specific_epithet,
    inputs.original_infraspecific_epithet,
    inputs.original_family,
    inputs.original_order,
    inputs.original_class,
    inputs.original_kingdom,
    inputs.original_taxon_rank,
    inputs.original_authorship,
    inputs.normalized_name,
    inputs.normalized_genus,
    inputs.normalized_epithet,
    inputs.normalized_infraspecific_epithet,
    inputs.normalized_family,
    inputs.normalized_rank,
    inputs.normalized_authorship,
    inputs.variant_count,
    inputs.occurrence_count,
    selected.accepted_id,
    selected.accepted_name,
    selected.accepted_authorship,
    selected.accepted_family,
    selected.accepted_status,
    selected.accepted_rank,
    selected.matched_usage_id,
    selected.matched_usage_name,
    selected.matched_usage_status,
    CASE WHEN selected.match_stage = 'species' THEN selected.candidate_method
         ELSE upper(selected.match_stage) || '_' || selected.candidate_method
    END AS selected_candidate_method,
    CASE
        WHEN inputs.reason_code IS NOT NULL OR selected.accepted_id IS NULL THEN 'UNMATCHED'
        WHEN selected.candidate_status = 'AMBIGUOUS' THEN 'AMBIGUOUS'
        ELSE selected_candidate_method
    END AS match_method,
    selected.match_score,
    CASE
        WHEN inputs.reason_code IS NOT NULL OR selected.accepted_id IS NULL THEN 'UNMATCHED'
        ELSE selected.candidate_status
    END AS update_status,
    inputs.reason_code,
    CASE WHEN selected.accepted_id IS NOT NULL
        THEN inputs.normalized_genus <> selected.accepted_genus
        ELSE false END AS genus_changed,
    CASE WHEN selected.accepted_id IS NOT NULL
        THEN coalesce(inputs.normalized_epithet <> selected.accepted_epithet, false)
        ELSE false END AS epithet_changed,
    coalesce(selected.candidate_count, 0)::INTEGER AS candidate_count,
    alternatives.alternative_matches,
    CASE WHEN selected.runner_up_score IS NOT NULL
        THEN selected.match_score - selected.runner_up_score END AS score_margin
FROM input_taxa inputs
LEFT JOIN selected USING (input_taxon_key)
LEFT JOIN alternatives USING (input_taxon_key)
ORDER BY inputs.input_taxon_key;
