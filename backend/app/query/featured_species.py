"""Featured species for the landing page: a daily sample of the most complete.

A species is scored by how much of its species page has something to show,
one point per facet:

* ``images``: at least ``MIN_IMAGES`` images.
* ``views``: both a dorsal and a ventral image.
* ``distribution``: at least one image with a validated country, the same
  population as the country diversity map.
* ``specimens``: at least one image with a catalogue number.
* ``commonName``: a vernacular name, from the image records or Catalogue of Life.
* ``traits``: a LepTraits consensus row.
* ``typeMaterial``: a Catalogue of Life type specimen record.
* ``similar``: a precomputed visually-similar-species panel.

The pool is the highest-scoring tiers, taken whole until it holds at least
``MIN_POOL`` species, and the sample is drawn from it with the UTC date as the
seed. Every worker therefore serves the same six species all day, and the set
changes at midnight UTC without any shared state between processes.

A facet whose source table was never built scores zero for every species
rather than failing, so the ranking degrades with the data instead of
disappearing.
"""

import logging
import random
from datetime import UTC, date, datetime, timedelta

import polars as pl

from ..configs.config import (
    ColConfig,
    ImageMetaConfig,
    LepTraitConfig,
    LocalityConfig,
    ProvenanceConfig,
)
from ..database.duckdb import DuckDBClient
from .precomputed_similarity import SIMILARITY_TABLE

logger = logging.getLogger(__name__)

MIN_IMAGES = 20
MIN_POOL = 24
MAX_LIMIT = 24

FACETS = (
    "images",
    "views",
    "distribution",
    "specimens",
    "commonName",
    "traits",
    "typeMaterial",
    "similar",
)

_LOCATED_CHECKS = ("COUNTRY_MATCH", "COUNTRY_NOT_PROVIDED")


def _text(column: str) -> str:
    return f"nullif(trim(cast({column} AS VARCHAR)), '')"


def seconds_until_rotation(now: datetime | None = None) -> int:
    """Seconds left before the sample changes, at the next UTC midnight."""
    now = now or datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int((tomorrow - now).total_seconds()))


class FeaturedSpecies:
    """Species completeness, scored once per process and sampled per day.

    The tables it reads are rebuilt only at startup or with the backend
    stopped, so the scores cannot change while the process runs.
    """

    def __init__(self, duckdb_client: DuckDBClient):
        self.db_client = duckdb_client
        col = ColConfig()
        self.images_table = ImageMetaConfig().table
        self.taxonomy_table = col.occurrence_status_table
        self.vernacular_table = col.vernacular_table
        self.type_material_table = col.type_material_table
        self.coordinates_table = LocalityConfig().coordinates_table
        self.provenance_table = ProvenanceConfig().table
        self.traits_table = LepTraitConfig().table
        self.similarity_table = SIMILARITY_TABLE
        self._scores: pl.DataFrame | None = None

    def available(self) -> bool:
        return not self.db_client.missing_tables(
            [self.images_table, self.taxonomy_table]
        )

    def _has(self, table: str) -> bool:
        return not self.db_client.missing_tables([table])

    def _score_query(self) -> str:
        located = (
            f"c.country_check IN ({', '.join(repr(c) for c in _LOCATED_CHECKS)})"
            if self._has(self.coordinates_table)
            else "false"
        )
        catalogued = (
            f"{_text('p.catalog_number')} IS NOT NULL"
            if self._has(self.provenance_table)
            else "false"
        )
        coordinates_join = (
            f"LEFT JOIN {self.coordinates_table} c ON c.source_id = i.img_id"
            if self._has(self.coordinates_table)
            else ""
        )
        provenance_join = (
            f"LEFT JOIN {self.provenance_table} p ON p.img_id = i.img_id"
            if self._has(self.provenance_table)
            else ""
        )

        def exists(table: str, condition: str) -> str:
            if not self._has(table):
                return "false"
            return f"EXISTS (SELECT 1 FROM {table} x WHERE {condition})"

        vernacular = exists(self.vernacular_table, "x.usage_id = sp.accepted_id")
        traits = exists(self.traits_table, "lower(x.Species) = lower(sp.species)")
        type_material = exists(self.type_material_table, "x.name_id = sp.accepted_id")
        similar = exists(self.similarity_table, "x.species = sp.slug")

        return f"""
            WITH img AS (
                SELECT
                    i.img_id,
                    i.species AS slug,
                    lower(i.class_dv) AS side,
                    coalesce(i.confidence_dv, 0) AS confidence,
                    coalesce({_text("t.accepted_species_name")},
                        CASE WHEN lower(t.accepted_rank) = 'species'
                            THEN {_text("t.accepted_name")} END) AS species,
                    t.accepted_id,
                    t.accepted_family AS family,
                    {located} AS located,
                    {catalogued} AS catalogued,
                    {_text("i.common_name")} IS NOT NULL AS has_common
                FROM {self.images_table} i
                JOIN {self.taxonomy_table} t USING (img_id)
                {coordinates_join}
                {provenance_join}
                WHERE t.update_status = 'MATCHED'
            ),
            sp AS (
                SELECT
                    species,
                    mode(family) AS family,
                    -- Species pages key on the recorded slug, not the
                    -- accepted name, so link through the commonest one.
                    mode(slug) AS slug,
                    mode(accepted_id) AS accepted_id,
                    count(*)::BIGINT AS image_count,
                    count(*) FILTER (WHERE side = 'dorsal') AS dorsal,
                    count(*) FILTER (WHERE side = 'ventral') AS ventral,
                    bool_or(located) AS located,
                    bool_or(catalogued) AS catalogued,
                    bool_or(has_common) AS has_common,
                    -- The most confidently dorsal image, the view the tiles
                    -- elsewhere on the site lead with; ties go to the lower id
                    -- so the choice is stable across restarts.
                    first(img_id ORDER BY side = 'dorsal' DESC, confidence DESC,
                        img_id) AS img_id
                FROM img
                WHERE species IS NOT NULL
                GROUP BY species
            )
            SELECT
                species, family, slug, img_id, image_count,
                image_count >= {MIN_IMAGES} AS images,
                dorsal > 0 AND ventral > 0 AS views,
                located AS distribution,
                catalogued AS specimens,
                has_common OR {vernacular} AS "commonName",
                {traits} AS traits,
                {type_material} AS "typeMaterial",
                {similar} AS similar
            FROM sp
        """

    def _load(self) -> pl.DataFrame:
        if self._scores is not None:
            return self._scores
        scores = self.db_client.execute(self._score_query()).pl()
        scores = scores.with_columns(
            pl.sum_horizontal(
                [pl.col(f).fill_null(False).cast(pl.Int8) for f in FACETS]
            )
            .cast(pl.Int64)
            .alias("score")
        ).sort(["score", "image_count", "species"], descending=[True, True, False])
        self._scores = scores
        logger.info(f"Scored {scores.height} species for the featured sample")
        return scores

    def _pool(self) -> pl.DataFrame:
        """The top score tiers, whole, until there are at least MIN_POOL species."""
        scores = self._load()
        if scores.is_empty():
            return scores
        tiers = scores["score"].unique().sort(descending=True)
        floor = tiers[0]
        for tier in tiers:
            floor = tier
            if scores.filter(pl.col("score") >= tier).height >= MIN_POOL:
                break
        return scores.filter(pl.col("score") >= floor)

    def sample(self, limit: int = 6, day: date | None = None) -> dict | None:
        """The day's featured species, the same for every call on that day."""
        if not self.available():
            return None
        pool = self._pool()
        if pool.is_empty():
            return None
        day = day or datetime.now(UTC).date()
        limit = max(1, min(limit, MAX_LIMIT, pool.height))
        # Sampled over the whole pool in a fixed order, so a larger limit on
        # the same day extends the smaller sample rather than replacing it.
        order = random.Random(day.isoformat()).sample(range(pool.height), pool.height)
        rows = pool[order[:limit]].to_dicts()
        return {
            "date": day.isoformat(),
            "poolSize": pool.height,
            "maxScore": len(FACETS),
            "species": [
                {
                    "species": row["species"],
                    "slug": row["slug"],
                    "family": row["family"],
                    "imgId": row["img_id"],
                    "imageCount": row["image_count"],
                    "score": row["score"],
                    "facets": [f for f in FACETS if row[f]],
                }
                for row in rows
            ],
        }
