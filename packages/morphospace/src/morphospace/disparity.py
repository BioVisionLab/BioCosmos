"""Disparity and dorso-ventral correlation, measured in the full embedding.

Nothing here uses the PCA: a two-dimensional picture keeps a fraction of the
variance, and disparity computed from it would inherit whatever the first two
axes happened to discard. Every input is a matrix of unit-length centroids,
one row per species.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial.distance import pdist, squareform


@dataclass(frozen=True)
class Disparity:
    n_species: int
    sum_var: float | None
    rarefied_mean: float | None
    rarefied_low: float | None
    rarefied_high: float | None


@dataclass(frozen=True)
class Mantel:
    n_species: int
    r: float | None
    p: float | None


def sum_of_variances(centroids: np.ndarray) -> float:
    """Trace of the covariance matrix: total spread around the scope's mean shape.

    For unit-length centroids this is exactly the mean pairwise cosine distance
    (see `mean_pairwise_distance`), so one number serves for both readings.
    """
    return float(centroids.astype(np.float64).var(axis=0, ddof=1).sum())


def mean_pairwise_distance(centroids: np.ndarray) -> float:
    """Mean cosine distance over all species pairs, in O(n·d).

    For unit vectors the sum of all pairwise dot products is ‖Σx‖² − n, so the
    n × n matrix is never built — and the result equals `sum_of_variances`,
    which is why the tables store only the latter.
    """
    n = len(centroids)
    total = centroids.astype(np.float64).sum(axis=0)
    similarity = (float(total @ total) - n) / (n * (n - 1))
    return 1.0 - similarity


def rarefied_sum_of_variances(
    centroids: np.ndarray, k: int, reps: int, rng: np.random.Generator
) -> tuple[float, float, float] | None:
    """Mean and 95% interval of disparity over random subsets of `k` species.

    Sum of variances is unbiased in richness, but its uncertainty is not: a
    genus of five is one noisy draw where a genus of forty is a stable average.
    Resampling every scope at the same `k` gives intervals that can be compared
    across genera of very different sizes.
    """
    n = len(centroids)
    if n < k:
        return None
    if n == k:
        value = sum_of_variances(centroids)
        return value, value, value
    data = centroids.astype(np.float64)
    values = np.empty(reps)
    for rep in range(reps):
        values[rep] = data[rng.choice(n, size=k, replace=False)].var(axis=0, ddof=1).sum()
    low, high = np.percentile(values, [2.5, 97.5])
    return float(values.mean()), float(low), float(high)


def disparity(centroids: np.ndarray, *, k: int, reps: int, rng: np.random.Generator) -> Disparity:
    n = len(centroids)
    if n < 2:
        return Disparity(n, None, None, None, None)
    rarefied = rarefied_sum_of_variances(centroids, k, reps, rng)
    return Disparity(
        n_species=n,
        sum_var=sum_of_variances(centroids),
        rarefied_mean=rarefied[0] if rarefied else None,
        rarefied_low=rarefied[1] if rarefied else None,
        rarefied_high=rarefied[2] if rarefied else None,
    )


def dorso_ventral_divergence(dorsal: np.ndarray, ventral: np.ndarray) -> np.ndarray:
    """Cosine distance between each species' dorsal and ventral centroid."""
    return 1.0 - np.einsum("ij,ij->i", dorsal.astype(np.float64), ventral.astype(np.float64))


def mantel(
    dorsal: np.ndarray,
    ventral: np.ndarray,
    *,
    permutations: int,
    rng: np.random.Generator,
    max_species: int,
    permutation_max_species: int,
) -> Mantel:
    """Correlation between the dorsal and ventral species distance matrices.

    High r: species that look alike from above also look alike from below, and
    the two surfaces vary together. Low r: they are decoupled — a conserved,
    cryptic underside under a divergent upperside, say. The p-value comes from
    permuting species labels on one side; it is skipped above
    `permutation_max_species`, and r itself above `max_species`, where the
    n × n matrices stop fitting comfortably in memory.
    """
    n = len(dorsal)
    if n < 3 or n > max_species:
        return Mantel(n, None, None)
    d = pdist(dorsal.astype(np.float64), "cosine")
    v = pdist(ventral.astype(np.float64), "cosine")
    # Permuting species only reorders the distances, so their mean and spread
    # are fixed and every r, observed or permuted, is one dot product with the
    # centered dorsal distances. Computing both the same way keeps exact ties.
    d -= d.mean()
    v -= v.mean()
    scale = float(np.sqrt(d @ d) * np.sqrt(v @ v))
    square = squareform(v).astype(np.float32)
    r = _correlation(d, square, np.arange(n), scale)
    if permutations <= 0 or n > permutation_max_species:
        return Mantel(n, r, None)
    exceed = 0
    for _ in range(permutations):
        if _correlation(d, square, rng.permutation(n), scale) >= r:
            exceed += 1
    return Mantel(n, r, (exceed + 1) / (permutations + 1))


def _correlation(
    centered: np.ndarray, square: np.ndarray, order: np.ndarray, scale: float
) -> float:
    """Pearson r of the centered distances against `square` with its species reordered."""
    if scale == 0:
        return 0.0
    permuted = squareform(square[np.ix_(order, order)], checks=False)
    return float(centered @ permuted) / scale
