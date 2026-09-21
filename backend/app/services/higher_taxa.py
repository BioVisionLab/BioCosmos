"""Data access for the family and genus pages.

A higher-taxon page asks three things of the database: which taxa sit below
this one, how much of the collection each of them accounts for, and which
images to show. All of it is answered here; `app/query/higher_taxa.py` turns
the rows into a payload and never writes SQL.

Membership is decided by the harmonized taxonomy, strictly: an image counts
towards a family or genus only when colharmonize resolved it (`update_status
= 'MATCHED'`), and it is the accepted name — not the recorded one — that says
where it belongs. The recorded name is still what identifies a species node,
because that is the key every species page and image query resolves on; see
`genus_members` for why that distinction is load-bearing rather than
pedantic.
"""

import logging
from typing import Literal

import duckdb

from ..configs.config import ColConfig, ImageMetaConfig
from ..database.duckdb import DuckDBClient

logger = logging.getLogger(__name__)


Scope = Literal["family", "genus"]

# Which harmonized column each page scopes on. Kept as a table rather than
# interpolating the caller's string: the scope reaches here from a URL.
_SCOPE_PREDICATE: dict[Scope, str] = {
    "family": "lower(t.accepted_family) = ?",
    "genus": "lower(split_part(t.accepted_name, ' ', 1)) = ?",
}


# The images that count towards a higher taxon, and the species each one
# belongs to.
#
# `accepted_species_name` is the grouping key throughout: it is the binomial
# colharmonize resolved the record to, so a subspecies record folds into its
# species and a misspelling folds into the name it was meant to be. Grouping
# on the recorded string instead would count `danaus_acleophile` as a species
# beside `danaus_cleophile`, which is the same butterfly spelled twice.
#
# It is deliberately not coalesced to `accepted_name`. colharmonize leaves it
# empty for a record it could only resolve to genus rank, and falling back
# would turn that empty into the genus name and count a bare genus as one of
# its own species.
_MATCHED_IMAGES = """
        SELECT o.img_id,
               o.species AS recorded_key,
               o.class_dv,
               t.accepted_species_name AS accepted_species,
               lower(split_part(t.accepted_name, ' ', 1)) AS genus_key,
               lower(t.accepted_family) AS family_key
        FROM {image_meta} o
        JOIN {status} t USING (img_id)
        WHERE t.update_status = 'MATCHED'
          AND t.accepted_name IS NOT NULL
"""

# Which recorded spelling a species node should link to: the one the most
# images were filed under. The species page resolves on the recorded string,
# so the node has to carry one of them rather than the accepted name, and the
# commonest is the one most likely to reach a populated page.
_DOMINANT_RECORD = """
    per_record AS (
        SELECT accepted_species, recorded_key, count(*) AS records
        FROM matched
        WHERE accepted_species IS NOT NULL
        GROUP BY accepted_species, recorded_key
    ), dominant AS (
        SELECT accepted_species, recorded_key
        FROM per_record
        QUALIFY row_number() OVER (
            PARTITION BY accepted_species
            ORDER BY records DESC, recorded_key
        ) = 1
    )
"""


def _clean_name(expression: str) -> str:
    """Tidy a name for display: no parenthesised subgenus, no double spaces.

    Catalogue of Life writes a zoological species as `Danaus (Danaus)
    plexippus`. The subgenus has a row of its own in the classification, so
    carrying it inside every name here only makes a tree harder to scan and
    harder to line up against the binomial the rest of the site uses.

    Whitespace is collapsed in the same pass because source names are not
    always tidy and the ingest normalizes the lookup keys but keeps
    `scientific_name` verbatim.
    """
    without_subgenus = f"regexp_replace({expression}, '\\([^)]*\\)', ' ', 'g')"
    return f"trim(regexp_replace({without_subgenus}, '\\s+', ' ', 'g'))"


class HigherTaxonRepository:
    """Read the members and representative images of a family or genus.

    Shaped like `ColTaxonSearch`: the optional tables are probed once per
    instance (an instance lives for one request) and every method degrades to
    an empty result rather than raising, so a missing ingestion costs a
    section of the page instead of the whole response.
    """

    # Class-level defaults so these are readable on an instance built without
    # __init__. Only ever rebound, never mutated.
    _col_present: bool | None = None
    _status_present: bool | None = None

    def __init__(self, duckdb_client: DuckDBClient):
        col_config = ColConfig()
        self.image_meta_table = ImageMetaConfig().table
        self.col_table = col_config.table
        self.status_table = col_config.occurrence_status_table
        self.db_client = duckdb_client
        self._col_present = None
        self._status_present = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def harmonized_available(self) -> bool:
        """Whether the per-occurrence harmonized taxonomy has been built.

        Membership is defined in terms of this table, so its absence is not a
        degraded page but no page at all: falling back to the recorded
        taxonomy would answer a different question than the one the counts
        claim to answer.
        """
        if self._status_present is None:
            self._status_present = self.db_client.table_exists(self.status_table)
            if not self._status_present:
                logger.warning(
                    f"'{self.status_table}' is missing; higher-taxon pages "
                    "cannot resolve membership and will report not found."
                )
        return self._status_present

    def col_available(self) -> bool:
        """Whether the CoL backbone has been ingested.

        Only placement and display depend on it. Without it the tree is flat
        and the names are title-cased keys, but the members and the counts
        are unchanged.
        """
        if self._col_present is None:
            self._col_present = self.db_client.table_exists(self.col_table)
        return self._col_present

    # ------------------------------------------------------------------
    # Members
    # ------------------------------------------------------------------

    def _matched_images(self) -> str:
        """The `matched` CTE body, bound to this instance's table names."""
        return _MATCHED_IMAGES.format(
            image_meta=self.image_meta_table, status=self.status_table
        )

    def family_members(self, family_key: str) -> list[dict]:
        """The genera of one family, with the CoL rank each sits under.

        Genera are rolled up from the accepted name rather than the recorded
        one, so a species CoL moved appears under the genus CoL moved it to
        and not under both.
        """
        if not self.harmonized_available():
            return []

        placement = ""
        projection = (
            "NULL AS authorship, NULL AS col_id, NULL AS col_link, "
            "NULL AS col_family, NULL AS subfamily, NULL AS tribe, NULL AS subtribe"
        )
        join = ""
        params: list = [family_key]

        if self.col_available():
            # 92 genus names in Lepidoptera have more than one accepted usage
            # in the backbone. Prefer the one CoL places in the family being
            # rendered; an unqualified join would multiply those rows.
            placement = f""",
    placement AS (
        SELECT genus_norm,
               usage_id,
               scientific_name,
               nullif(trim(authorship), '') AS authorship,
               nullif(trim(subfamily), '')  AS subfamily,
               nullif(trim(tribe), '')      AS tribe,
               nullif(trim(subtribe), '')   AS subtribe,
               family_norm,
               col_link
        FROM {self.col_table}
        WHERE taxon_rank = 'genus'
          AND is_accepted
          AND genus_norm IN (SELECT genus_key FROM rollup)
        QUALIFY row_number() OVER (
            PARTITION BY genus_norm
            ORDER BY (family_norm = ?) DESC NULLS LAST, usage_id
        ) = 1
    )"""
            projection = (
                "p.authorship, p.usage_id AS col_id, p.col_link, "
                "p.family_norm AS col_family, p.subfamily, p.tribe, p.subtribe"
            )
            join = "LEFT JOIN placement p ON p.genus_norm = r.genus_key"
            params.append(family_key)

        # `scientific_name` is preferred for display because it carries CoL's
        # own casing; the title-cased key is only a fallback. DuckDB has no
        # initcap().
        name_expr = _clean_name(
            "coalesce(p.scientific_name, "
            "concat(upper(left(r.genus_key, 1)), substr(r.genus_key, 2)))"
            if self.col_available()
            else "concat(upper(left(r.genus_key, 1)), substr(r.genus_key, 2))"
        )

        query = f"""
    WITH matched AS ({self._matched_images()}
          AND lower(t.accepted_family) = ?
    ), rollup AS (
        SELECT genus_key,
               -- A record identified only to genus is an image of a specimen
               -- but not of a species, so it counts once in the gallery and
               -- not at all in the species tally.
               count(DISTINCT accepted_species) AS species_count,
               count(*)                         AS image_count
        FROM matched
        WHERE genus_key <> ''
        GROUP BY genus_key
    ){placement}
    SELECT r.genus_key,
           {name_expr} AS genus_name,
           {projection},
           r.species_count,
           r.image_count
    FROM rollup r
    {join}
    ORDER BY r.image_count DESC, r.genus_key
        """
        return self._rows(query, params, f"family members for '{family_key}'")

    def genus_members(self, genus_key: str) -> list[dict]:
        """The species of one genus, each linked to the name it is filed under.

        One node per accepted species, because that is what strict
        harmonization means: a subspecies record and a misspelling both fold
        into the species they resolve to, instead of standing beside it under
        a name a reader cannot tell apart from it.

        The node still *links* on a recorded spelling. A species page looks
        its images up by `image_meta.species`, so an href built from the
        accepted name would render a header over an empty gallery wherever
        Catalogue of Life has renamed the taxon.
        """
        if not self.harmonized_available():
            return []

        placement = ""
        projection = (
            "NULL AS authorship, NULL AS col_id, NULL AS col_link, "
            "NULL AS col_status, NULL AS subgenus"
        )
        join = ""
        params: list = [genus_key]

        if self.col_available():
            # canonical_key, not scientific_name: Catalogue of Life writes
            # zoological names with the subgenus in parentheses, so only the
            # canonical form matches an accepted binomial.
            placement = f""",
    placement AS (
        SELECT canonical_key,
               usage_id,
               scientific_name,
               nullif(trim(authorship), '') AS authorship,
               nullif(trim(subgenus), '')   AS subgenus,
               status,
               col_link
        FROM {self.col_table}
        WHERE genus_norm = ?
          AND taxon_rank IN ('species', 'subspecies')
          AND canonical_key IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY canonical_key
            ORDER BY is_accepted DESC, usage_id
        ) = 1
    )"""
            projection = (
                "p.authorship, p.usage_id AS col_id, p.col_link, "
                "p.status AS col_status, p.subgenus"
            )
            join = (
                "LEFT JOIN placement p ON p.canonical_key = lower(s.accepted_species)"
            )
            params.append(genus_key)

        # CoL's own spelling when we have it, because it carries the subgenus
        # parenthetical the harmonized name drops; the accepted name otherwise.
        name_expr = _clean_name(
            "coalesce(p.scientific_name, s.accepted_species)"
            if self.col_available()
            else "s.accepted_species"
        )

        query = f"""
    WITH matched AS ({self._matched_images()}
          AND lower(split_part(t.accepted_name, ' ', 1)) = ?
          AND t.accepted_species_name IS NOT NULL
    ), {_DOMINANT_RECORD}, scoped AS (
        SELECT m.accepted_species,
               d.recorded_key,
               count(*) AS image_count
        FROM matched m
        JOIN dominant d USING (accepted_species)
        GROUP BY m.accepted_species, d.recorded_key
    ){placement}
    SELECT s.recorded_key AS species_key,
           {name_expr} AS species_name,
           concat(upper(left(replace(s.recorded_key, '_', ' '), 1)),
                  substr(replace(s.recorded_key, '_', ' '), 2)) AS recorded_name,
           {projection},
           s.image_count
    FROM scoped s
    {join}
    ORDER BY s.accepted_species
        """
        return self._rows(query, params, f"genus members for '{genus_key}'")

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def representative_images(
        self, scope: Scope, key: str, limit: int = 20
    ) -> list[dict]:
        """One image of each of up to `limit` species.

        One per species, never two. The strip sits under a heading saying
        these are the species in the group, so a second specimen of the
        best-photographed one would put the same name in the grid twice and
        contradict it. A taxon with fewer species than the limit shows fewer
        tiles, which is the honest answer rather than a padded one.

        Deterministic. These responses are cached for thirty days behind an
        ETag, so the same URL has to return the same images for the life of
        that cache.
        """
        if not self.harmonized_available():
            return []
        predicate = _SCOPE_PREDICATE[scope]

        query = f"""
    WITH matched AS ({self._matched_images()}
          AND {predicate}
          AND t.accepted_species_name IS NOT NULL
    ), {_DOMINANT_RECORD}, counted AS (
        SELECT accepted_species, count(*) AS image_count
        FROM matched GROUP BY accepted_species
    ), top_species AS (
        SELECT accepted_species, image_count
        FROM counted
        ORDER BY image_count DESC, accepted_species
        LIMIT ?
    ), ranked AS (
        SELECT m.img_id,
               d.recorded_key,
               m.accepted_species,
               c.image_count,
               row_number() OVER (
                   PARTITION BY m.accepted_species
                   -- Dorsal is the canonical spread-wing view; a grid of
                   -- ventral shots reads as a different organism. Unknown
                   -- vocabulary degrades to ordering by img_id.
                   ORDER BY (lower(m.class_dv) = 'dorsal') DESC NULLS LAST,
                            m.img_id
               ) AS within_species
        FROM matched m
        JOIN top_species c USING (accepted_species)
        JOIN dominant d USING (accepted_species)
    )
    SELECT img_id,
           recorded_key AS species,
           accepted_species AS display_name
    FROM ranked
    WHERE within_species = 1
    ORDER BY image_count DESC, accepted_species
        """
        return self._rows(
            query,
            [key, limit],
            f"representative images for {scope} '{key}'",
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _rows(self, query: str, params: list, description: str) -> list[dict]:
        """Run a statement, or log and return nothing.

        Every caller renders a section of a page, so a failure here should
        cost that section and not the response.
        """
        try:
            result = self.db_client.execute_prepared_to_pl(query, params)
        except duckdb.Error as error:
            logger.error(f"Query failed for {description}: {error}")
            return []
        if result is None or result.is_empty():
            logger.info(f"No rows for {description}")
            return []
        return result.to_dicts()
