"""Which species page a record links to.

A species page looks its images up by the name the collection recorded
(`image_meta.species`), and it renders for any name at all: a synonym, a
misspelling or a name Catalogue of Life never resolved still gets a page,
just an orphaned one — a partial or empty gallery, no classification, and
nothing in the collection tree that leads to it.

So a link to a species has to be chosen, not derived from whatever string a
record happens to carry. The choice made here is the one the order, family
and genus pages already make: a record belongs to the accepted species
colharmonize resolved it to, and that species has exactly one page, under the
recorded spelling most of its images were filed under. A record that did not
resolve to a species has no page to link to, and callers leave it out.

The SQL fragments live here rather than in `higher_taxa.py` so the tree and
the search results cannot disagree about which page is canonical.
"""

import logging
from collections.abc import Iterable, Sequence

import duckdb
import polars as pl

from ..configs.config import ColConfig, ImageMetaConfig
from ..database.duckdb import DuckDBClient

logger = logging.getLogger(__name__)

# The images that count towards a species, and the species each one belongs
# to.
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
#
# Such a record is left out entirely, from the image counts as much as the
# species tally: every count on these pages is of images of a valid species.
# Counting them in a family's rollup but not on the genus page is how a
# family linked to a genus page that answered 404 — `allancastria_cerisyi`,
# resolved to the genus alone, gave Allancastria 45 images and no species.
MATCHED_IMAGES = """
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
          AND t.accepted_species_name IS NOT NULL
"""

# Which recorded spelling a species node should link to: the one the most
# images were filed under. The species page resolves on the recorded string,
# so the node has to carry one of them rather than the accepted name, and the
# commonest is the one most likely to reach a populated page.
#
# A two-word spelling is preferred over any count of trinomial or subgenus
# ones. The species route is a binomial and matches the recorded string
# exactly, so `danaus_plexippus_plexippus` would be cut to `danaus_plexippus`
# on the way into a URL and open a gallery holding none of its images.
# `is_binomial` says whether the winner is one; a species filed only under
# longer spellings has no page a link can reach.
DOMINANT_RECORD = """
    per_record AS (
        SELECT accepted_species,
               recorded_key,
               count(*) AS records,
               regexp_full_match(recorded_key, '[^\\s_()]+[\\s_]+[^\\s_()]+')
                   AS is_binomial
        FROM matched
        WHERE accepted_species IS NOT NULL
        GROUP BY accepted_species, recorded_key
    ), dominant AS (
        SELECT accepted_species, recorded_key, is_binomial
        FROM per_record
        QUALIFY row_number() OVER (
            PARTITION BY accepted_species
            ORDER BY is_binomial DESC, records DESC, recorded_key
        ) = 1
    )
"""

_LOOKUP_CHUNK = 500


def _normalize_recorded(name: str) -> str:
    return "_".join(name.strip().lower().replace("_", " ").split())


class SpeciesPageResolver:
    """Map records onto the species page they belong to.

    Every method returns only what resolved. A record missing from the result
    has no valid page: it was never harmonized, stopped at genus rank, or its
    species is filed only under spellings the route cannot reach.

    When no harmonization run has been loaded there is nothing to resolve
    against. `available` says so, and callers fall back to the recorded
    names rather than hiding every result.
    """

    # Class-level default so the field is readable on an instance built
    # without __init__. Only ever rebound, never mutated.
    _status_present: bool | None = None

    def __init__(self, duckdb_client: DuckDBClient):
        self.image_meta_table = ImageMetaConfig().table
        self.status_table = ColConfig().occurrence_status_table
        self.db_client = duckdb_client
        self._status_present = None

    def available(self) -> bool:
        """Whether a harmonization run has been loaded to resolve against."""
        if self._status_present is None:
            self._status_present = self.db_client.table_exists(self.status_table)
        return self._status_present

    def page_keys_for_images(self, img_ids: Iterable[str]) -> dict[str, str]:
        """The species page of each image, keyed by image id."""
        unique_ids = list(dict.fromkeys(str(i) for i in img_ids if i))
        if not unique_ids or not self.available():
            return {}
        keys: dict[str, str] = {}
        for chunk in _chunks(unique_ids):
            rows = self._resolve("img_id", chunk)
            keys.update({row["lookup"]: row["species_key"] for row in rows})
        return keys

    def page_keys_for_species(self, names: Iterable[str]) -> dict[str, str]:
        """The species page of each recorded name, keyed by the name as given.

        A name filed against differing higher taxonomy can resolve more than
        one way; it links to the species most of its records resolved to.
        """
        by_normalized: dict[str, list[str]] = {}
        for name in names:
            if name:
                by_normalized.setdefault(_normalize_recorded(name), []).append(name)
        if not by_normalized or not self.available():
            return {}
        keys: dict[str, str] = {}
        for chunk in _chunks(list(by_normalized)):
            rows = self._resolve("lower(replace(recorded_key, ' ', '_'))", chunk)
            for row in rows:
                for name in by_normalized.get(row["lookup"], []):
                    keys[name] = row["species_key"]
        return keys

    def _resolve(self, lookup: str, values: Sequence[str]) -> list[dict]:
        """One row per looked-up value that reaches a valid page.

        `lookup` is a fixed expression over the matched columns, chosen by the
        caller in this module and never from a request.

        The dominant spelling is computed only over the species the requested
        records resolve to, not the whole collection: it is the same answer
        for those species, for the cost of a handful of groups.
        """
        placeholders = ", ".join("?" for _ in values)
        matched = MATCHED_IMAGES.format(
            image_meta=self.image_meta_table, status=self.status_table
        )
        query = f"""
    WITH everything AS ({matched}
    ), wanted AS (
        SELECT {lookup} AS lookup, accepted_species, count(*) AS records
        FROM everything
        WHERE {lookup} IN ({placeholders})
        GROUP BY 1, 2
        QUALIFY row_number() OVER (
            PARTITION BY {lookup} ORDER BY count(*) DESC, accepted_species
        ) = 1
    ), matched AS (
        SELECT * FROM everything
        WHERE accepted_species IN (SELECT accepted_species FROM wanted)
    ), {DOMINANT_RECORD}
    SELECT w.lookup, d.recorded_key AS species_key
    FROM wanted w
    JOIN dominant d USING (accepted_species)
    WHERE d.is_binomial
        """
        try:
            result = self.db_client.execute_prepared_to_pl(query, list(values))
        except duckdb.Error as error:
            logger.error(f"Species page lookup failed: {error}")
            return []
        if result is None or result.is_empty():
            return []
        return result.to_dicts()


def recorded_binomial_key(species: pl.Expr) -> pl.Expr:
    """The binomial route key of a recorded name, or null for a genus.

    Only for a database with no harmonization run, where there is no accepted
    species to find a page for and the recorded name is all there is.
    """
    parts = (
        species.cast(pl.String)
        .str.to_lowercase()
        .str.replace_all(r"[\s_]+", " ")
        .str.strip_chars()
        .str.split(" ")
    )
    return (
        pl.when(parts.list.len() >= 2)
        .then(parts.list.slice(0, 2).list.join("_"))
        .otherwise(None)
    )


def attach_page_keys(
    results: pl.DataFrame,
    pages: SpeciesPageResolver,
    *,
    img_column: str = "imgId",
    species_column: str = "species",
) -> pl.DataFrame:
    """Add a `speciesKey` column, the page each result links to.

    Rows with no valid page are dropped, since the only link they could carry
    is to an orphaned page. Without a harmonization run nothing can be
    resolved, so the recorded binomial stands in and a genus-only record is
    kept with no link, as results were shown before.
    """
    if results.is_empty() or img_column not in results.columns:
        return results.with_columns(pl.lit(None, pl.String).alias("speciesKey"))
    if not pages.available():
        return results.with_columns(
            recorded_binomial_key(pl.col(species_column)).alias("speciesKey")
        )
    keys = pages.page_keys_for_images(results[img_column].cast(pl.String))
    return results.with_columns(
        pl.col(img_column)
        .cast(pl.String)
        .replace_strict(keys, default=None, return_dtype=pl.String)
        .alias("speciesKey")
    ).filter(pl.col("speciesKey").is_not_null())


def _chunks(values: list[str]) -> Iterable[list[str]]:
    for start in range(0, len(values), _LOOKUP_CHUNK):
        yield values[start : start + _LOOKUP_CHUNK]
