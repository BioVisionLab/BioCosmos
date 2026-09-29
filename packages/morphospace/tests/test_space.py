import numpy as np
import polars as pl
import pytest

from morphospace.disparity import mantel
from morphospace.groups import Groups, build_groups
from morphospace.space import COMPONENTS, Scope, fit_space


def _unit(rows: np.ndarray) -> np.ndarray:
    return rows / np.linalg.norm(rows, axis=1, keepdims=True)


def _labels(rows: list[tuple[str, str, str]]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "img_id": img_id,
                "side": side,
                "accepted_species": species,
                "page_key": species.lower().replace(" ", "_"),
                "genus_key": species.split()[0].lower(),
                "genus_name": species.split()[0],
                "family_key": "testidae",
                "family_name": "Testidae",
            }
            for img_id, side, species in rows
        ]
    )


def test_groups_are_numbered_in_sorted_order():
    labels = _labels(
        [
            ("b_v", "ventral", "Beta one"),
            ("a_d", "dorsal", "Alpha one"),
            ("b_d", "dorsal", "Beta one"),
        ]
    )
    groups = build_groups(labels)
    assert groups.taxa["accepted_species"].to_list() == ["Alpha one", "Beta one"]
    assert groups.groups.select("species_id", "side").rows() == [
        (0, "dorsal"),
        (1, "dorsal"),
        (1, "ventral"),
    ]
    matched = groups.lookup(pl.Series(["missing", "b_v", "a_d"]))
    assert matched.select("row", "group_id").rows() == [(1, 2), (2, 0)]


def test_side_groups_marks_missing_sides():
    labels = _labels([("a_d", "dorsal", "Alpha one"), ("b_v", "ventral", "Beta one")])
    groups = build_groups(labels)
    table = groups.side_groups(np.array([True, True]))
    assert table.tolist() == [[0, -1], [-1, 1]]


def _scope(count: int) -> tuple[Scope, Groups, np.ndarray]:
    rows = [
        (f"{n}_{side}", side, f"Alpha s{n}") for n in range(count) for side in ("dorsal", "ventral")
    ]
    groups = build_groups(_labels(rows))
    scope = Scope("genus", "alpha", "Alpha", None, np.arange(count), np.arange(groups.size))
    centroids = _unit(np.random.default_rng(count).normal(size=(groups.size, 6)))
    return scope, groups, centroids.astype(np.float32)


def test_fit_space_pins_the_largest_loading_positive():
    scope, groups, centroids = _scope(4)
    space = fit_space(scope, groups, centroids)
    assert space.basis == "both_sides"
    assert space.explained.sum() <= 1.0 + 1e-9
    for column in range(COMPONENTS):
        loadings = space.components[:, column]
        assert loadings[np.argmax(np.abs(loadings))] > 0


def test_fit_space_pads_components_it_cannot_fit():
    scope, groups, centroids = _scope(1)  # two centroids: at most two components
    space = fit_space(scope, groups, centroids)
    assert space.basis == "all_centroids"
    assert space.components.shape == (6, COMPONENTS)
    assert np.allclose(space.components[:, 2], 0) and space.explained[2] == 0
    assert space.project(centroids).shape == (2, COMPONENTS)


def test_mantel_r_matches_brute_force_pearson():
    rng = np.random.default_rng(1)
    dorsal = _unit(rng.normal(size=(12, 8)))
    ventral = _unit(dorsal + 0.5 * rng.normal(size=(12, 8)))
    upper = np.triu_indices(12, k=1)
    expected = np.corrcoef((1 - dorsal @ dorsal.T)[upper], (1 - ventral @ ventral.T)[upper])[0, 1]
    result = mantel(
        dorsal, ventral, permutations=0, rng=rng, max_species=100, permutation_max_species=100
    )
    assert result.r == pytest.approx(expected)
