"""Scopes and their shared dorso-ventral principal-component spaces.

A scope is a set of species viewed together: the whole collection, one
family, or one genus. Each scope gets its own PCA, fitted on the dorsal and
ventral centroids *stacked*, so both sides live on the same axes and the
dorsal-to-ventral offset of a species is a vector in that space rather than a
jump between two unrelated plots.

PCA rather than UMAP: the axes are linear combinations of the embedding with
a stated share of variance, distances along them mean the same thing
everywhere, and a rerun on the same data gives the same picture.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from morphospace.centroids import GroupIndex
from morphospace.models import SIDES

COMPONENTS = 3


@dataclass
class Scope:
    rank: str
    key: str
    name: str
    parent_family: str | None
    species: np.ndarray  # species numbers in the scope with at least one kept group
    groups: np.ndarray  # kept groups of those species
    basis: str = ""
    mean: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    components: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.float32))
    explained: np.ndarray = field(default_factory=lambda: np.zeros(COMPONENTS))
    both_sides: int = 0

    def project(self, vectors: np.ndarray) -> np.ndarray:
        return (vectors - self.mean) @ self.components


def enumerate_scopes(
    index: GroupIndex, keep: np.ndarray, *, min_species: int
) -> dict[str, list[Scope]]:
    """Every scope with at least `min_species` species that have a kept group."""
    taxa = index.taxa
    kept_groups = np.flatnonzero(keep)
    kept_species = np.unique(index.group_species[kept_groups])

    def make(rank: str, key: str, name: str, parent: str | None, species: np.ndarray):
        groups = kept_groups[np.isin(index.group_species[kept_groups], species)]
        return Scope(rank, key, name, parent, species, groups)

    scopes: dict[str, list[Scope]] = {"all": [], "family": [], "genus": []}
    if len(kept_species) >= min_species:
        scopes["all"].append(make("all", "all", "All species", None, kept_species))

    for rank, key_column, name_column in (
        ("family", taxa.family_key, taxa.family_name),
        ("genus", taxa.genus_key, taxa.genus_name),
    ):
        keys = key_column[kept_species]
        present = np.array([k is not None and k != "" for k in keys], dtype=bool)
        members = kept_species[present]
        member_keys = keys[present].astype(str)
        for key in np.unique(member_keys):
            species = members[member_keys == key]
            if len(species) < min_species:
                continue
            first = species[0]
            family = taxa.family_name[first]
            parent = str(family) if rank == "genus" and family else None
            scopes[rank].append(make(rank, key, str(name_column[first]), parent, species))
    return scopes


def fit(scope: Scope, index: GroupIndex, centroids: np.ndarray) -> None:
    """Fit the scope's shared dorso-ventral PCA in place.

    Fitted on the species seen from both sides when there are enough of them,
    so that a species with only a dorsal photograph does not pull the axes
    towards dorsal-only variation. Species with one side are still projected.
    """
    group_species = index.group_species[scope.groups]
    group_side = index.group_side[scope.groups]
    sides_per_species = {
        s: len(np.unique(group_side[group_species == s])) for s in np.unique(group_species)
    }
    both = np.array([sides_per_species[s] == len(SIDES) for s in group_species], dtype=bool)
    scope.both_sides = int(sum(1 for n in sides_per_species.values() if n == len(SIDES)))
    if scope.both_sides >= 3:
        basis_groups, scope.basis = scope.groups[both], "both_sides"
    else:
        basis_groups, scope.basis = scope.groups, "all_centroids"

    data = centroids[basis_groups].astype(np.float64)
    mean = data.mean(axis=0)
    _, singular, vt = np.linalg.svd(data - mean, full_matrices=False)
    variance = singular**2
    total = variance.sum()
    count = min(COMPONENTS, vt.shape[0])
    components = np.zeros((data.shape[1], COMPONENTS))
    components[:, :count] = vt[:count].T
    # SVD signs are arbitrary. Pinning the largest loading positive makes a
    # rerun on the same data draw the same picture, not its mirror image.
    for column in range(count):
        pivot = np.argmax(np.abs(components[:, column]))
        if components[pivot, column] < 0:
            components[:, column] *= -1
    explained = np.zeros(COMPONENTS)
    if total > 0:
        explained[:count] = variance[:count] / total
    scope.mean = mean.astype(np.float32)
    scope.components = components.astype(np.float32)
    scope.explained = explained


class EllipseAccumulator:
    """Second pass: moments of each group's images in each rank's scope space.

    A species is in at most one scope per rank, so one array per rank indexed
    by group holds every scope of that rank at once.
    """

    def __init__(self, index: GroupIndex, scopes: dict[str, list[Scope]]) -> None:
        self.index = index
        self.scopes = scopes
        species_count = len(index.taxa)
        self.scope_of_species: dict[str, np.ndarray] = {}
        self.moments: dict[str, np.ndarray] = {}
        for rank, members in scopes.items():
            lookup = np.full(species_count, -1, dtype=np.int64)
            for number, scope in enumerate(members):
                lookup[scope.species] = number
            self.scope_of_species[rank] = lookup
            # n, Σx, Σy, Σx², Σy², Σxy
            self.moments[rank] = np.zeros((index.size, 6), dtype=np.float64)

    def add(self, groups: np.ndarray, vectors: np.ndarray) -> None:
        species = self.index.group_species[groups]
        size = self.index.size
        for rank, members in self.scopes.items():
            scope_numbers = self.scope_of_species[rank][species]
            rows = np.flatnonzero(scope_numbers >= 0)
            if len(rows) == 0:
                continue
            # Sort once so each scope is one contiguous slice, then project the
            # slices and accumulate every scope of the rank in one bincount.
            rows = rows[np.argsort(scope_numbers[rows], kind="stable")]
            numbers = scope_numbers[rows]
            starts = np.flatnonzero(np.r_[True, numbers[1:] != numbers[:-1]])
            ends = np.r_[starts[1:], len(rows)]
            xy = np.empty((len(rows), 2), dtype=np.float64)
            for start, end in zip(starts, ends, strict=True):
                block = rows[start:end]
                xy[start:end] = members[numbers[start]].project(vectors[block])[:, :2]
            x, y, g = xy[:, 0], xy[:, 1], groups[rows]
            moments = self.moments[rank]
            for column, weights in enumerate((None, x, y, x * x, y * y, x * y)):
                moments[:, column] += np.bincount(g, weights=weights, minlength=size)

    def ellipse(self, rank: str, group: int) -> tuple[float, float, float, float, float]:
        """Mean x, mean y, SD x, SD y and correlation of one group's images."""
        n, sx, sy, sxx, syy, sxy = self.moments[rank][group]
        if n == 0:
            return (float("nan"),) * 5  # type: ignore[return-value]
        mx, my = sx / n, sy / n
        vx = max(sxx / n - mx * mx, 0.0)
        vy = max(syy / n - my * my, 0.0)
        cov = sxy / n - mx * my
        rho = cov / np.sqrt(vx * vy) if vx > 0 and vy > 0 else 0.0
        return mx, my, float(np.sqrt(vx)), float(np.sqrt(vy)), float(np.clip(rho, -1, 1))
