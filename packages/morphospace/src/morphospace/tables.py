"""The five artifact tables, built from the groups, centroids and per-image pass-2 frame.

Column names, order and types are the contract with the backend
(backend/app/query/morphospace.py) and analyses/; the schemas below pin them.
"""

from __future__ import annotations

from dataclasses import asdict

import numpy as np
import polars as pl

from morphospace.disparity import disparity, dorso_ventral_divergence, mantel
from morphospace.groups import Groups
from morphospace.models import SIDES, MorphospaceParameters
from morphospace.space import RANKS, Scope, ScopeSpace

_S, _F, _I = pl.String, pl.Float64, pl.Int64
_SCOPE_KEY = {"scope_rank": _S, "scope_key": _S}

SCOPE_SCHEMA = pl.Schema(
    {
        **_SCOPE_KEY,
        "scope_name": _S,
        "parent_family": _S,
        "n_species": _I,
        "n_species_both": _I,
        "basis": _S,
        "explained_pc1": _F,
        "explained_pc2": _F,
        "explained_pc3": _F,
        "dv_mantel_n": _I,
        "dv_mantel_r": _F,
        "dv_mantel_p": _F,
        "run_id": _S,
    }
)
POINT_SCHEMA = pl.Schema(
    {
        **_SCOPE_KEY,
        "accepted_species": _S,
        "page_key": _S,
        "genus_key": _S,
        "family_key": _S,
        "side": _S,
        "n_images": _I,
        "pc1": _F,
        "pc2": _F,
        "pc3": _F,
        "ell_x": _F,
        "ell_y": _F,
        "ell_sx": _F,
        "ell_sy": _F,
        "ell_rho": _F,
        "img_id": _S,
    }
)
SPECIES_SCHEMA = pl.Schema(
    {
        "accepted_species": _S,
        "page_key": _S,
        "genus_key": _S,
        "genus_name": _S,
        "family_key": _S,
        "family_name": _S,
        **{
            f"{side}_{column}": kind
            for side in SIDES
            for column, kind in (("n", _I), ("dispersion", _F), ("img_id", _S))
        },
        "dv_divergence": _F,
    }
)
DISPARITY_SCHEMA = pl.Schema(
    {
        **_SCOPE_KEY,
        "side": _S,
        "n_species": _I,
        "sum_var": _F,
        "rarefied_mean": _F,
        "rarefied_low": _F,
        "rarefied_high": _F,
        "rarefy_k": _I,
    }
)
EXTREME_SCHEMA = pl.Schema(
    {
        **_SCOPE_KEY,
        "axis": _S,
        "end": _S,
        "accepted_species": _S,
        "page_key": _S,
        "side": _S,
        "img_id": _S,
        "value": _F,
    }
)
_TEXT_COLUMNS = ("page_key", "genus_key", "genus_name", "family_key", "family_name")
_AXES = ("pc1", "pc2", "pc3")


def conform(frame: pl.DataFrame, schema: pl.Schema) -> pl.DataFrame:
    """Exactly the schema's columns, in its order and with its types."""

    return frame.select(pl.col(name).cast(kind) for name, kind in schema.items())


def _blank_to_null(frame: pl.DataFrame) -> pl.DataFrame:
    present = [name for name in _TEXT_COLUMNS if name in frame.columns]

    return frame.with_columns(
        pl.when(pl.col(name) == "").then(None).otherwise(pl.col(name)).alias(name)
        for name in present
    )


def group_stats(images: pl.DataFrame) -> pl.DataFrame:
    """Per group: mean cosine distance to the centroid, and the medoid image."""

    return images.group_by("group_id").agg(
        dispersion=(1.0 - pl.col("similarity")).mean(),
        img_id=pl.col("img_id").get(pl.col("similarity").arg_max()),
    )


def ellipse_stats(images: pl.DataFrame) -> pl.DataFrame:
    """Mean, SD and correlation of each group's images in each rank's scope space."""

    frames = []

    for rank in RANKS:
        x, y = pl.col(f"{rank}_x"), pl.col(f"{rank}_y")
        frames.append(
            images.filter(x.is_not_nan())
            .group_by("group_id")
            .agg(
                ell_x=x.mean(),
                ell_y=y.mean(),
                ell_sx=x.std(ddof=0),
                ell_sy=y.std(ddof=0),
                ell_rho=pl.corr(x, y),
            )
            .with_columns(
                pl.lit(rank).alias("scope_rank"),
                pl.col("ell_rho").fill_nan(0.0).fill_null(0.0).clip(-1.0, 1.0),
            )
        )

    return pl.concat(frames)


def kept_groups(
    groups: Groups, counts: np.ndarray, keep: np.ndarray, stats: pl.DataFrame
) -> pl.DataFrame:
    """The kept groups with their image count, dispersion and medoid."""

    return (
        groups.groups.with_columns(n_images=pl.Series(counts, dtype=pl.Int64))
        .filter(pl.Series(keep))
        .join(stats, on="group_id", how="left", maintain_order="left")
    )


def species_table(
    groups: Groups, kept: pl.DataFrame, centroids: np.ndarray, side_groups: np.ndarray
) -> pl.DataFrame:
    """One row per species, both sides side by side."""

    species_ids = np.unique(kept["species_id"].to_numpy())
    frame = groups.taxa.filter(pl.col("species_id").is_in(species_ids.tolist())).sort("species_id")

    for side in SIDES:
        frame = frame.join(
            kept.filter(pl.col("side") == side).select(
                "species_id",
                pl.col("n_images").alias(f"{side}_n"),
                pl.col("dispersion").alias(f"{side}_dispersion"),
                pl.col("img_id").alias(f"{side}_img_id"),
            ),
            on="species_id",
            how="left",
            maintain_order="left",
        )

    dorsal, ventral = side_groups[species_ids, 0], side_groups[species_ids, 1]
    both = (dorsal >= 0) & (ventral >= 0)
    divergence = np.full(len(species_ids), np.nan)
    divergence[both] = dorso_ventral_divergence(centroids[dorsal[both]], centroids[ventral[both]])
    frame = frame.with_columns(dv_divergence=pl.Series(divergence).fill_nan(None))

    return conform(_blank_to_null(frame), SPECIES_SCHEMA)


def points_frame(
    groups: Groups,
    kept: pl.DataFrame,
    centroids: np.ndarray,
    scopes: dict[str, list[Scope]],
    spaces: dict[str, list[ScopeSpace]],
    ellipses: pl.DataFrame,
) -> pl.DataFrame:
    """Every kept group placed in every scope it belongs to, in scope order."""

    frames = []

    for rank in RANKS:
        for scope, space in zip(scopes[rank], spaces[rank], strict=True):
            projected = space.project(centroids[scope.groups])
            frames.append(
                pl.DataFrame(
                    {
                        "scope_order": len(frames),
                        "scope_rank": rank,
                        "scope_key": scope.key,
                        "group_id": scope.groups,
                        **{axis: projected[:, n] for n, axis in enumerate(_AXES)},
                    },
                    schema_overrides={axis: pl.Float64 for axis in _AXES},
                )
            )

    if not frames:
        return pl.DataFrame(schema={"scope_order": pl.Int64, **POINT_SCHEMA})

    return _blank_to_null(
        pl.concat(frames)
        .join(
            kept.select("group_id", "species_id", "side", "n_images", "img_id"),
            on="group_id",
            maintain_order="left",
        )
        .join(groups.taxa, on="species_id", maintain_order="left")
        .join(ellipses, on=["scope_rank", "group_id"], how="left", maintain_order="left")
    )


def extremes_table(points: pl.DataFrame, scope: pl.DataFrame) -> pl.DataFrame:
    """The species at the low and high end of every axis with explained variance."""

    keys = ["scope_order", "scope_rank", "scope_key", "axis"]
    fields = ["accepted_species", "page_key", "side", "img_id", "value"]
    explained = scope.unpivot(
        on=[f"explained_{axis}" for axis in _AXES],
        index=["scope_rank", "scope_key"],
        variable_name="axis",
        value_name="explained",
    ).with_columns(pl.col("axis").str.strip_prefix("explained_"))

    values = (
        points.unpivot(
            on=list(_AXES),
            index=["scope_order", "scope_rank", "scope_key", *fields[:-1]],
            variable_name="axis",
            value_name="value",
        )
        .join(explained, on=["scope_rank", "scope_key", "axis"], maintain_order="left")
        .filter(pl.col("explained") != 0)
        .group_by(keys, maintain_order=True)
    )

    ends = pl.concat(
        [
            values.agg(pl.col(fields).get(pl.col("value").arg_min())).with_columns(
                end=pl.lit("min"), end_order=0
            ),
            values.agg(pl.col(fields).get(pl.col("value").arg_max())).with_columns(
                end=pl.lit("max"), end_order=1
            ),
        ]
    )

    return conform(ends.sort("scope_order", "axis", "end_order"), EXTREME_SCHEMA)


def scope_metrics(
    run_id: str,
    groups: Groups,
    centroids: np.ndarray,
    scopes: dict[str, list[Scope]],
    spaces: dict[str, list[ScopeSpace]],
    side_groups: np.ndarray,
    parameters: MorphospaceParameters,
    rng: np.random.Generator,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """The scope and disparity tables.

    Scope by scope, dorsal disparity, then ventral, then the Mantel test, so a
    seed draws the same random numbers into the same place on every run.
    """

    group_side = groups.group_side
    scope_rows: list[dict] = []
    disparity_rows: list[dict] = []

    for rank in RANKS:
        for scope, space in zip(scopes[rank], spaces[rank], strict=True):
            key = {"scope_rank": rank, "scope_key": scope.key}

            for side_number, side in enumerate(SIDES):
                side_groups_in_scope = scope.groups[group_side[scope.groups] == side_number]
                result = disparity(
                    centroids[side_groups_in_scope],
                    k=parameters.rarefy_k,
                    reps=parameters.bootstrap,
                    rng=rng,
                )
                disparity_rows.append(
                    {**key, "side": side, **asdict(result), "rarefy_k": parameters.rarefy_k}
                )

            pairs = side_groups[scope.species]
            pairs = pairs[(pairs >= 0).all(axis=1)]
            correlation = None

            if len(pairs) >= parameters.mantel_min_species:
                correlation = mantel(
                    centroids[pairs[:, 0]],
                    centroids[pairs[:, 1]],
                    permutations=parameters.permutations,
                    rng=rng,
                    max_species=parameters.mantel_max_species,
                    permutation_max_species=parameters.permutation_max_species,
                )

            scope_rows.append(
                {
                    **key,
                    "scope_name": scope.name,
                    "parent_family": scope.parent_family or None,
                    "n_species": len(scope.species),
                    "n_species_both": len(pairs),
                    "basis": space.basis,
                    **{
                        f"explained_{axis}": float(space.explained[n])
                        for n, axis in enumerate(_AXES)
                    },
                    "dv_mantel_n": correlation.n_species if correlation else len(pairs),
                    "dv_mantel_r": correlation.r if correlation else None,
                    "dv_mantel_p": correlation.p if correlation else None,
                    "run_id": run_id,
                }
            )

    return (
        pl.DataFrame(scope_rows, schema=SCOPE_SCHEMA),
        pl.DataFrame(disparity_rows, schema=DISPARITY_SCHEMA),
    )
