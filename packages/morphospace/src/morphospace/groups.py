"""Species × side groups, and their centroids accumulated from streamed embedding batches.

A *group* is one species seen from one side. Everything downstream works on
groups: a species is placed in a morphospace by its group centroids, and its
intraspecific spread is measured within each group.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl
from scipy import sparse

from morphospace.models import SIDES

TAXON_COLUMNS = (
    "accepted_species",
    "page_key",
    "genus_key",
    "genus_name",
    "family_key",
    "family_name",
)


@dataclass(frozen=True)
class Groups:
    """The species, their groups, and which group each labelled image belongs to.

    `taxa` has one row per `species_id`, `groups` one row per `group_id`, both
    numbered in a stable (sorted) order, and `images` maps `img_id` to its group.
    """

    taxa: pl.DataFrame
    groups: pl.DataFrame
    images: pl.DataFrame

    @property
    def size(self) -> int:
        return self.groups.height

    @property
    def group_species(self) -> np.ndarray:
        return self.groups["species_id"].to_numpy()

    @property
    def group_side(self) -> np.ndarray:
        """Index into SIDES of each group."""

        return self.groups["side_index"].to_numpy()

    def lookup(self, img_ids: pl.Series) -> pl.DataFrame:
        """`row` (position in `img_ids`), `img_id` and `group_id` of the labelled images."""

        return (
            pl.DataFrame({"img_id": img_ids.cast(pl.String)})
            .with_row_index("row")
            .join(self.images, on="img_id", how="inner", maintain_order="left")
        )

    def side_groups(self, keep: np.ndarray) -> np.ndarray:
        """`(species, side)` -> kept group number, or -1 where that side has none."""

        table = np.full((self.taxa.height, len(SIDES)), -1, dtype=np.int64)
        kept = np.flatnonzero(keep)
        table[self.group_species[kept], self.group_side[kept]] = kept

        return table


def build_groups(labels: pl.DataFrame) -> Groups:
    """Number the species and their sides in a stable (sorted) order."""

    # The first image of each species carries its page key and higher taxa;
    # they are functions of the accepted species, so any row would do.
    taxa = (
        labels.group_by("accepted_species", maintain_order=True)
        .agg(pl.col(TAXON_COLUMNS[1:]).first())
        .sort("accepted_species")
        .with_row_index("species_id")
    )
    images = (
        labels.unique("img_id", keep="last", maintain_order=True)
        .join(taxa.select("accepted_species", "species_id"), on="accepted_species")
        .with_columns(
            side_index=pl.col("side").replace_strict(
                SIDES, range(len(SIDES)), return_dtype=pl.Int64
            )
        )
    )
    groups = (
        images.select("species_id", "side_index", "side")
        .unique()
        .sort("species_id", "side_index")
        .with_row_index("group_id")
    )

    return Groups(
        taxa=taxa.with_columns(pl.col("species_id").cast(pl.Int64)),
        groups=groups.with_columns(pl.col("group_id", "species_id").cast(pl.Int64)),
        images=images.join(groups, on=["species_id", "side_index"])
        .select("img_id", pl.col("group_id").cast(pl.Int64))
        .with_columns(pl.col("img_id").cast(pl.String)),
    )


class CentroidAccumulator:
    """First pass: per-group vector sums and image counts."""

    def __init__(self, groups: Groups, width: int) -> None:
        self.groups = groups
        self.sums = np.zeros((groups.size, width), dtype=np.float64)
        self.counts = np.zeros(groups.size, dtype=np.int64)
        self.embedded = 0

    def add(self, img_ids: pl.Series, vectors: np.ndarray) -> None:
        matched = self.groups.lookup(img_ids)

        if matched.height == 0:
            return

        rows = matched["row"].to_numpy()
        group_ids = matched["group_id"].to_numpy()
        # A sparse group × image indicator sums each group's rows in one product.
        indicator = sparse.csr_array(
            (np.ones(len(rows)), (group_ids, rows)), shape=(self.groups.size, len(vectors))
        )
        self.sums += indicator @ vectors
        self.counts += np.bincount(group_ids, minlength=self.groups.size)
        self.embedded += len(rows)

    def centroids(self, min_images: int) -> tuple[np.ndarray, np.ndarray]:
        """Unit-length centroids, and which groups have enough images to keep."""

        keep = self.counts >= min_images
        norms = np.linalg.norm(self.sums, axis=1, keepdims=True)
        norms[norms == 0] = 1.0

        return (self.sums / norms).astype(np.float32), keep
