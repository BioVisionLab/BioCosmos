"""Disparity and dorso-ventral integration, measured in the full embedding.

Nothing here uses the PCA: a two-dimensional picture keeps a fraction of the
variance, and disparity computed from it would inherit whatever the first two
axes happened to discard. Every input is a matrix of unit-length centroids,
one row per species.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


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
    d = 1.0 - dorsal.astype(np.float32) @ dorsal.astype(np.float32).T
    v = 1.0 - ventral.astype(np.float32) @ ventral.astype(np.float32).T
    upper = np.triu_indices(n, k=1)
    x = d[upper].astype(np.float64)
    x -= x.mean()
    x_norm = np.sqrt(x @ x)

    def correlate(matrix: np.ndarray) -> float:
        y = matrix[upper].astype(np.float64)
        y -= y.mean()
        denominator = x_norm * np.sqrt(y @ y)
        return float(x @ y / denominator) if denominator > 0 else 0.0

    r = correlate(v)
    if permutations <= 0 or n > permutation_max_species:
        return Mantel(n, r, None)
    exceed = 0
    for _ in range(permutations):
        order = rng.permutation(n)
        if correlate(v[np.ix_(order, order)]) >= r:
            exceed += 1
    return Mantel(n, r, (exceed + 1) / (permutations + 1))
