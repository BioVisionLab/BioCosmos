"""SQL-first taxonomic matching pipeline."""

from __future__ import annotations

from pathlib import Path

import duckdb

from colharmonize.identifiers import qualified_name, quote_identifier, quote_literal
from colharmonize.models import MatchingConfig
from colharmonize.sources import OccurrenceSource
from colharmonize.sql import read_sql


def _source_expr(columns: dict[str, str], logical: str) -> str:
    physical = columns.get(logical)
    return "NULL::VARCHAR" if physical is None else f"cast({quote_identifier(physical)} AS VARCHAR)"


class MatchPipeline:
    """Execute set-based extraction, candidate generation, and ranking."""

    def __init__(
        self,
        connection: duckdb.DuckDBPyConnection,
        occurrence: OccurrenceSource,
        resolved_columns: dict[str, str],
        reference_index: Path,
        matching: MatchingConfig,
    ) -> None:
        self.connection = connection
        self.occurrence = occurrence
        self.columns = resolved_columns
        self.reference_index = reference_index
        self.matching = matching

    def run(self) -> None:
        self._attach_sources()
        self._extract_inputs()
        self._generate_candidates()
        self._collapse_and_rank()
        self._create_matches()

    def _attach_sources(self) -> None:
        self.connection.execute(
            f"ATTACH {quote_literal(str(self.occurrence.database))} "
            "AS occurrence_source (READ_ONLY)"
        )
        self.connection.execute(
            f"ATTACH {quote_literal(str(self.reference_index))} AS reference_source (READ_ONLY)"
        )

    def _extract_inputs(self) -> None:
        source_table = (
            f"{quote_identifier('occurrence_source')}.{qualified_name(self.occurrence.identifier)}"
        )
        expressions = {
            key: _source_expr(self.columns, key)
            for key in (
                "scientific_name",
                "genus",
                "specific_epithet",
                "family",
                "order",
                "class",
                "kingdom",
                "taxon_rank",
                "authorship",
            )
        }
        source_name = (
            f"coalesce({expressions['scientific_name']}, "
            f"concat_ws(' ', {expressions['genus']}, {expressions['specific_epithet']}))"
        )
        self.connection.execute(
            f"""
            CREATE TABLE input_taxon_variants AS
            WITH raw AS (
                SELECT
                    {source_name} AS original_scientific_name,
                    {expressions["genus"]} AS original_genus,
                    {expressions["specific_epithet"]} AS original_specific_epithet,
                    {expressions["family"]} AS original_family,
                    {expressions["order"]} AS original_order,
                    {expressions["class"]} AS original_class,
                    {expressions["kingdom"]} AS original_kingdom,
                    {expressions["taxon_rank"]} AS original_taxon_rank,
                    {expressions["authorship"]} AS original_authorship,
                    count(*)::BIGINT AS occurrence_count
                FROM {source_table}
                GROUP BY ALL
            ), cleaned AS (
                SELECT *,
                    lower(regexp_replace(trim(replace(original_scientific_name, '_', ' ')),
                        '\\s+', ' ', 'g')) AS normalized_name,
                    regexp_replace(
                        lower(regexp_replace(trim(replace(original_scientific_name, '_', ' ')),
                            '\\s+', ' ', 'g')),
                        '\\s*\\([^)]+\\)\\s*', ' ', 'g') AS parse_name,
                    lower(nullif(trim(original_genus), '')) AS structured_genus_norm,
                    lower(nullif(trim(original_specific_epithet), '')) AS structured_epithet_norm,
                    lower(nullif(trim(original_family), '')) AS family_norm,
                    lower(coalesce(nullif(trim(original_taxon_rank), ''), 'species')) AS rank_norm,
                    lower(regexp_replace(trim(original_authorship), '\\s+', ' ', 'g'))
                        AS authorship_norm,
                    lower(nullif(trim(original_order), '')) AS order_norm,
                    lower(nullif(trim(original_class), '')) AS class_norm,
                    lower(nullif(trim(original_kingdom), '')) AS kingdom_norm
                FROM raw
            ), normalized AS (
                SELECT *,
                    coalesce(structured_genus_norm,
                        nullif(regexp_extract(parse_name, '^\\s*([^ ]+)', 1), '')) AS genus_norm,
                    coalesce(structured_epithet_norm,
                        nullif(regexp_extract(parse_name, '^\\s*[^ ]+\\s+([^ ]+)', 1), ''))
                        AS epithet_norm
                FROM cleaned
            ), keyed AS (
                SELECT *,
                    concat(genus_norm, ' ', epithet_norm) AS canonical_key,
                    sha256(to_json(struct_pack(
                        normalized_name := normalized_name,
                        genus := genus_norm,
                        epithet := epithet_norm,
                        family := family_norm,
                        taxon_rank := rank_norm,
                        authorship := authorship_norm,
                        order_name := order_norm,
                        class_name := class_norm,
                        kingdom := kingdom_norm
                    ))) AS input_taxon_key,
                    CASE
                        WHEN rank_norm <> 'species' THEN 'UNSUPPORTED_RANK'
                        WHEN genus_norm IS NULL OR epithet_norm IS NULL
                          OR NOT regexp_matches(genus_norm, '^[[:alpha:]×-]+$')
                          OR NOT regexp_matches(epithet_norm, '^[[:alpha:]×-]+$')
                        THEN 'INVALID_BINOMIAL'
                        ELSE NULL
                    END AS reason_code
                FROM normalized
            )
            SELECT
                input_taxon_key,
                original_scientific_name,
                original_genus,
                original_specific_epithet,
                original_family,
                original_order,
                original_class,
                original_kingdom,
                original_taxon_rank,
                original_authorship,
                normalized_name,
                genus_norm,
                epithet_norm,
                canonical_key,
                family_norm,
                rank_norm,
                authorship_norm,
                order_norm,
                class_norm,
                kingdom_norm,
                reason_code,
                occurrence_count
            FROM keyed
            """
        )
        self.connection.execute(
            """
            CREATE TABLE input_taxa AS
            SELECT
                input_taxon_key,
                min(original_scientific_name) AS original_scientific_name,
                min(original_genus) AS original_genus,
                min(original_specific_epithet) AS original_specific_epithet,
                min(original_family) AS original_family,
                min(original_order) AS original_order,
                min(original_class) AS original_class,
                min(original_kingdom) AS original_kingdom,
                min(original_taxon_rank) AS original_taxon_rank,
                min(original_authorship) AS original_authorship,
                min(normalized_name) AS normalized_name,
                min(genus_norm) AS normalized_genus,
                min(epithet_norm) AS normalized_epithet,
                min(canonical_key) AS canonical_key,
                min(family_norm) AS normalized_family,
                min(rank_norm) AS normalized_rank,
                min(authorship_norm) AS normalized_authorship,
                min(order_norm) AS normalized_order,
                min(class_norm) AS normalized_class,
                min(kingdom_norm) AS normalized_kingdom,
                min(reason_code) AS reason_code,
                count(*)::INTEGER AS variant_count,
                sum(occurrence_count)::BIGINT AS occurrence_count
            FROM input_taxon_variants
            GROUP BY input_taxon_key
            """
        )

    def _generate_candidates(self) -> None:
        config = self.matching
        common = """
            i.input_taxon_key,
            a.accepted_id,
            a.accepted_name,
            a.accepted_authorship,
            a.accepted_genus,
            a.accepted_epithet,
            a.accepted_family,
            a.accepted_status,
            {usage_id} AS matched_usage_id,
            {usage_name} AS matched_usage_name,
            {usage_status} AS matched_usage_status,
            {method} AS generation_method,
            {tier}::INTEGER AS tier,
            (i.normalized_family IS NOT NULL
                AND i.normalized_family = a.family_norm)::INTEGER AS family_exact,
            (i.normalized_rank = a.taxon_rank)::INTEGER AS rank_exact,
            (i.normalized_authorship IS NOT NULL AND a.authorship_norm IS NOT NULL
                AND i.normalized_authorship = a.authorship_norm)::INTEGER AS authorship_exact,
            damerau_levenshtein(i.normalized_genus, a.accepted_genus)::INTEGER
                AS genus_distance,
            damerau_levenshtein(i.normalized_epithet, a.accepted_epithet)::INTEGER
                AS epithet_distance,
            jaro_winkler_similarity(i.normalized_genus, a.accepted_genus)
                AS genus_similarity,
            jaro_winkler_similarity(i.normalized_epithet, a.accepted_epithet)
                AS epithet_similarity
        """
        accepted_common = common.format(
            usage_id="a.accepted_id",
            usage_name="a.accepted_name",
            usage_status="a.accepted_status",
            method="{method}",
            tier="{tier}",
        )
        exact_usage = common.format(
            usage_id="u.usage_id",
            usage_name="u.usage_name",
            usage_status="u.usage_status",
            method=(
                "CASE WHEN lower(u.usage_status) IN ('accepted', 'provisionally accepted') "
                "THEN 'EXACT_ACCEPTED' ELSE 'EXACT_SYNONYM' END"
            ),
            tier=(
                "CASE WHEN lower(u.usage_status) IN ('accepted', 'provisionally accepted') "
                "THEN 1 ELSE 2 END"
            ),
        )
        self.connection.execute(
            f"""
            CREATE TABLE raw_candidates AS
            SELECT {exact_usage}
            FROM input_taxa i
            JOIN reference_source.usage_lookup u
              ON i.normalized_name = u.usage_name_norm
            JOIN reference_source.accepted_taxa a ON a.accepted_id = u.accepted_id
            WHERE i.reason_code IS NULL

            UNION ALL
            SELECT {accepted_common.format(method="'EXACT_CANONICAL'", tier="3")}
            FROM input_taxa i
            JOIN reference_source.accepted_taxa a ON i.canonical_key = a.canonical_key
            WHERE i.reason_code IS NULL

            UNION ALL
            SELECT {accepted_common.format(method="'FAMILY_EPITHET'", tier="8")}
            FROM input_taxa i
            JOIN reference_source.accepted_taxa a
              ON i.normalized_family = a.family_norm
             AND i.normalized_epithet = a.accepted_epithet
            WHERE i.reason_code IS NULL AND i.normalized_family IS NOT NULL

            UNION ALL
            SELECT {accepted_common.format(method="'SPELLING_GENUS'", tier="5")}
            FROM input_taxa i
            JOIN reference_source.accepted_taxa a
              ON i.normalized_family = a.family_norm
             AND i.normalized_epithet = a.accepted_epithet
             AND abs(length(i.normalized_genus) - length(a.accepted_genus)) <= 2
            WHERE i.reason_code IS NULL
              AND i.normalized_genus <> a.accepted_genus
              AND (damerau_levenshtein(i.normalized_genus, a.accepted_genus)
                        <= {config.genus_distance}
                   OR jaro_winkler_similarity(i.normalized_genus, a.accepted_genus)
                        >= {config.min_genus_similarity})

            UNION ALL
            SELECT {accepted_common.format(method="'SPELLING_EPITHET'", tier="6")}
            FROM input_taxa i
            JOIN reference_source.accepted_taxa a
              ON i.normalized_family = a.family_norm
             AND i.normalized_genus = a.accepted_genus
             AND abs(length(i.normalized_epithet) - length(a.accepted_epithet)) <= 2
            WHERE i.reason_code IS NULL
              AND i.normalized_epithet <> a.accepted_epithet
              AND damerau_levenshtein(i.normalized_epithet, a.accepted_epithet) <= CASE
                    WHEN length(i.normalized_epithet) <= {config.short_epithet_length}
                    THEN {config.short_epithet_distance}
                    ELSE {config.long_epithet_distance} END

            UNION ALL
            SELECT {accepted_common.format(method="'FUZZY_TYPO'", tier="7")}
            FROM input_taxa i
            JOIN reference_source.accepted_taxa a
              ON i.normalized_family = a.family_norm
             AND abs(length(i.normalized_genus) - length(a.accepted_genus)) <= 2
             AND abs(length(i.normalized_epithet) - length(a.accepted_epithet)) <= 2
            WHERE i.reason_code IS NULL
              AND i.normalized_genus <> a.accepted_genus
              AND i.normalized_epithet <> a.accepted_epithet
              AND (damerau_levenshtein(i.normalized_genus, a.accepted_genus)
                        <= {config.genus_distance}
                   OR jaro_winkler_similarity(i.normalized_genus, a.accepted_genus)
                        >= {config.min_genus_similarity})
              AND damerau_levenshtein(i.normalized_epithet, a.accepted_epithet) <= CASE
                    WHEN length(i.normalized_epithet) <= {config.short_epithet_length}
                    THEN {config.short_epithet_distance}
                    ELSE {config.long_epithet_distance} END
            """
        )

    def _collapse_and_rank(self) -> None:
        self.connection.execute(read_sql("collapse_candidates.sql"))
        self.connection.execute(read_sql("rank_candidates.sql"))
        self.connection.execute(
            """
            CREATE TABLE taxonomy_candidates AS
            SELECT
                input_taxon_key,
                candidate_rank,
                candidate_count,
                accepted_id,
                accepted_name,
                accepted_authorship,
                accepted_genus,
                accepted_epithet,
                accepted_family,
                accepted_status,
                matched_usage_id,
                matched_usage_name,
                matched_usage_status,
                candidate_method,
                generation_methods,
                match_score,
                family_exact::BOOLEAN AS family_exact,
                rank_exact::BOOLEAN AS rank_exact,
                authorship_exact::BOOLEAN AS authorship_exact,
                genus_distance,
                epithet_distance,
                genus_similarity,
                epithet_similarity
            FROM ranked_candidates
            WHERE candidate_rank <= ?
            ORDER BY input_taxon_key, candidate_rank
            """,
            [self.matching.top_k],
        )

    def _create_matches(self) -> None:
        sql = read_sql("create_matches.sql").replace(
            ":min_score_margin", str(self.matching.min_score_margin)
        )
        self.connection.execute(sql)
