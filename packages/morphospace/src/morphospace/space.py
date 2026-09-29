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

from dataclasses import dataclass

import numpy as np
import polars as pl
from sklearn.decomposition import PCA

from morphospace.groups import Groups
from morphospace.models import SIDES

COMPONENTS = 3
RANKS = ("all", "family", "genus")


@dataclass(frozen=True)
class Scope:
    rank: str
    key: str
    name: str
    parent_family: str | None
    species: np.ndarray  # species numbers in the scope with at least one kept group
    groups: np.ndarray  # kept groups of those species


@dataclass(frozen=True)
class ScopeSpace:
    """A scope's fitted PCA, padded to `COMPONENTS` axes."""

    basis: str
    both_sides: int
    mean: np.ndarray
    components: np.ndarray  # (width, COMPONENTS)
    explained: np.ndarray  # (COMPONENTS,)

    def project(self, vectors: np.ndarray) -> np.ndarray:
        return (vectors - self.mean) @ self.components


def _make_scope(
    rank: str,
    key: str,
    name: str,
    parent: str | None,
    species: np.ndarray,
    kept_groups: np.ndarray,
    group_species: np.ndarray,
) -> Scope:
    groups = kept_groups[np.isin(group_species[kept_groups], species)]
    return Scope(rank, key, name, parent, species, groups)


def enumerate_scopes(
    groups: Groups, keep: np.ndarray, *, min_species: int
) -> dict[str, list[Scope]]:
    """Every scope with at least `min_species` species that have a kept group."""
    group_species = groups.group_species
    kept_groups = np.flatnonzero(keep)
    kept_species = np.unique(group_species[kept_groups])

    scopes: dict[str, list[Scope]] = {rank: [] for rank in RANKS}
    if len(kept_species) >= min_species:
        scopes["all"].append(
            _make_scope("all", "all", "All species", None, kept_species, kept_groups, group_species)
        )

    kept_taxa = groups.taxa.filter(pl.col("species_id").is_in(kept_species.tolist()))
    for rank in ("family", "genus"):
        members = (
            kept_taxa.filter(pl.col(f"{rank}_key").fill_null("") != "")
            .sort("species_id")
            .group_by(f"{rank}_key")
            .agg(
                pl.col("species_id"),
                pl.col(f"{rank}_name").first().alias("name"),
                pl.col("family_name").first(),
            )
            .filter(pl.col("species_id").list.len() >= min_species)
            .sort(f"{rank}_key")
        )
        for key, species, name, family in members.iter_rows():
            parent = str(family) if rank == "genus" and family else None
            scopes[rank].append(
                _make_scope(
                    rank,
                    key,
                    str(name),
                    parent,
                    np.asarray(species, dtype=np.int64),
                    kept_groups,
                    group_species,
                )
            )
    return scopes


def fit_space(scope: Scope, groups: Groups, centroids: np.ndarray) -> ScopeSpace:
    """Fit the scope's shared dorso-ventral PCA.

    Fitted on the species seen from both sides when there are enough of them,
    so that a species with only a dorsal photograph does not pull the axes
    towards dorsal-only variation. Species with one side are still projected.
    """
    group_species = groups.group_species[scope.groups]
    species, sides = np.unique(group_species, return_counts=True)
    paired = species[sides == len(SIDES)]
    if len(paired) >= 3:
        basis_groups, basis = scope.groups[np.isin(group_species, paired)], "both_sides"
    else:
        basis_groups, basis = scope.groups, "all_centroids"

    data = centroids[basis_groups].astype(np.float64)
    count = min(COMPONENTS, *data.shape)
    # With the full solver, sklearn pins each component's largest loading
    # positive, so a rerun on the same data draws the same picture, not its
    # mirror image.
    pca = PCA(n_components=count, svd_solver="full").fit(data)
    components = np.zeros((data.shape[1], COMPONENTS))
    components[:, :count] = np.asarray(pca.components_).T
    explained = np.zeros(COMPONENTS)
    explained[:count] = np.nan_to_num(pca.explained_variance_ratio_)
    return ScopeSpace(
        basis=basis,
        both_sides=len(paired),
        mean=pca.mean_.astype(np.float32),
        components=components.astype(np.float32),
        explained=explained,
    )


def scope_lookup(scopes: list[Scope], species_count: int) -> np.ndarray:
    """Species number -> position of its scope in `scopes`, or -1.

    A species is in at most one scope per rank, so one array covers the rank.
    """
    lookup = np.full(species_count, -1, dtype=np.int64)
    for number, scope in enumerate(scopes):
        lookup[scope.species] = number
    return lookup


def project_rank(
    spaces: list[ScopeSpace], scope_numbers: np.ndarray, vectors: np.ndarray
) -> np.ndarray:
    """PC1 and PC2 of each vector in its scope's space; NaN outside every scope."""
    xy = np.full((len(vectors), 2), np.nan)
    rows = np.flatnonzero(scope_numbers >= 0)
    if len(rows) == 0:
        return xy
    # Sort once so each scope is one contiguous slice, then project the slices.
    rows = rows[np.argsort(scope_numbers[rows], kind="stable")]
    numbers = scope_numbers[rows]
    starts = np.flatnonzero(np.r_[True, numbers[1:] != numbers[:-1]])
    ends = np.r_[starts[1:], len(rows)]
    for start, end in zip(starts, ends, strict=True):
        block = rows[start:end]
        xy[block] = spaces[numbers[start]].project(vectors[block])[:, :2]
    return xy
