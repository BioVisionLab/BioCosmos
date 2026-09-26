"""Species × side centroids, accumulated from streamed embedding batches.

A *group* is one species seen from one side. Everything downstream works on
groups: a species is placed in a morphospace by its group centroids, and its
intraspecific spread is measured within each group.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from morphospace.models import SIDES
from morphospace.sources import Labels


@dataclass(frozen=True)
class Taxa:
    """One entry per species, as parallel arrays indexed by species number."""

    accepted_species: np.ndarray
    page_key: np.ndarray
    genus_key: np.ndarray
    genus_name: np.ndarray
    family_key: np.ndarray
    family_name: np.ndarray

    def __len__(self) -> int:
        return len(self.accepted_species)


@dataclass(frozen=True)
class GroupIndex:
    """Which group each labelled image belongs to."""

    taxa: Taxa
    group_species: np.ndarray  # (G,) species number of each group
    group_side: np.ndarray  # (G,) index into SIDES
    image_group: dict[str, int]

    @property
    def size(self) -> int:
        return len(self.group_species)

    def lookup(self, img_ids: np.ndarray) -> np.ndarray:
        """Group number of each image id, or -1 for an unlabelled image."""
        get = self.image_group.get
        return np.fromiter((get(i, -1) for i in img_ids), dtype=np.int64, count=len(img_ids))


def build_index(labels: Labels) -> GroupIndex:
    """Number the species and their sides in a stable (sorted) order."""
    # The first image of each species carries its page key and higher taxa;
    # they are functions of the accepted species, so any row would do.
    species_names, first, species_of_image = np.unique(
        labels.accepted_species.astype(str), return_index=True, return_inverse=True
    )
    taxa = Taxa(
        accepted_species=species_names.astype(object),
        page_key=labels.page_key[first],
        genus_key=labels.genus_key[first],
        genus_name=labels.genus_name[first],
        family_key=labels.family_key[first],
        family_name=labels.family_name[first],
    )
    side_of_image = np.array([SIDES.index(side) for side in labels.side], dtype=np.int64)
    combined = species_of_image.astype(np.int64) * len(SIDES) + side_of_image
    codes, group_of_image = np.unique(combined, return_inverse=True)
    return GroupIndex(
        taxa=taxa,
        group_species=codes // len(SIDES),
        group_side=codes % len(SIDES),
        image_group=dict(zip(labels.img_id.tolist(), group_of_image.tolist(), strict=True)),
    )


def grouped_sum(groups: np.ndarray, values: np.ndarray, size: int) -> np.ndarray:
    """Sum rows of `values` by group, without the cost of `np.add.at`."""
    order = np.argsort(groups, kind="stable")
    sorted_groups = groups[order]
    starts = np.flatnonzero(np.r_[True, sorted_groups[1:] != sorted_groups[:-1]])
    out = np.zeros((size, values.shape[1]), dtype=np.float64)
    out[sorted_groups[starts]] = np.add.reduceat(values[order], starts, axis=0)
    return out


class CentroidAccumulator:
    """First pass: per-group vector sums and image counts."""

    def __init__(self, index: GroupIndex, width: int) -> None:
        self.index = index
        self.sums = np.zeros((index.size, width), dtype=np.float64)
        self.counts = np.zeros(index.size, dtype=np.int64)
        self.embedded = 0

    def add(self, img_ids: np.ndarray, vectors: np.ndarray) -> None:
        groups = self.index.lookup(img_ids)
        labelled = groups >= 0
        if not labelled.any():
            return
        groups, vectors = groups[labelled], vectors[labelled]
        self.embedded += len(groups)
        self.sums += grouped_sum(groups, vectors, self.index.size)
        self.counts += np.bincount(groups, minlength=self.index.size)

    def centroids(self, min_images: int) -> tuple[np.ndarray, np.ndarray]:
        """Unit-length centroids, and which groups have enough images to keep."""
        keep = self.counts >= min_images
        norms = np.linalg.norm(self.sums, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (self.sums / norms).astype(np.float32), keep
