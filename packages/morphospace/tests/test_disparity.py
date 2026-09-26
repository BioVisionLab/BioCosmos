import numpy as np
import pytest

from morphospace.disparity import (
    disparity,
    dorso_ventral_divergence,
    mantel,
    mean_pairwise_distance,
    rarefied_sum_of_variances,
    sum_of_variances,
)


def _unit(rows: np.ndarray) -> np.ndarray:
    return rows / np.linalg.norm(rows, axis=1, keepdims=True)


def test_sum_of_variances_matches_covariance_trace():
    data = np.random.default_rng(0).normal(size=(20, 5))
    assert sum_of_variances(data) == pytest.approx(np.trace(np.cov(data, rowvar=False)))


def test_mean_pairwise_distance_matches_explicit_matrix():
    data = _unit(np.random.default_rng(1).normal(size=(12, 6)))
    similarity = data @ data.T
    upper = np.triu_indices(len(data), k=1)
    assert mean_pairwise_distance(data) == pytest.approx(1 - similarity[upper].mean())
    # The identity the tables rely on to store only one of the two.
    assert mean_pairwise_distance(data) == pytest.approx(sum_of_variances(data))


def test_rarefaction_is_exact_at_k_and_absent_below_it():
    data = np.random.default_rng(2).normal(size=(5, 4))
    rng = np.random.default_rng(0)
    exact = rarefied_sum_of_variances(data, 5, 50, rng)
    assert exact == pytest.approx((sum_of_variances(data),) * 3)
    assert rarefied_sum_of_variances(data, 6, 50, rng) is None


def test_rarefied_interval_brackets_mean():
    data = np.random.default_rng(3).normal(size=(40, 4))
    mean, low, high = rarefied_sum_of_variances(data, 5, 200, np.random.default_rng(0))
    assert low <= mean <= high


def test_disparity_needs_two_species():
    result = disparity(np.ones((1, 3)), k=5, reps=10, rng=np.random.default_rng(0))
    assert result.n_species == 1 and result.sum_var is None


def test_identical_sides_have_no_divergence_and_perfect_integration():
    data = _unit(np.random.default_rng(4).normal(size=(10, 8)))
    assert np.allclose(dorso_ventral_divergence(data, data), 0, atol=1e-6)
    result = mantel(
        data,
        data,
        permutations=99,
        rng=np.random.default_rng(0),
        max_species=100,
        permutation_max_species=100,
    )
    assert result.r == pytest.approx(1.0)
    assert result.p == pytest.approx(1 / 100)


def test_mantel_skips_permutations_above_limit():
    data = _unit(np.random.default_rng(5).normal(size=(10, 8)))
    result = mantel(
        data,
        data,
        permutations=99,
        rng=np.random.default_rng(0),
        max_species=100,
        permutation_max_species=5,
    )
    assert result.r is not None and result.p is None
