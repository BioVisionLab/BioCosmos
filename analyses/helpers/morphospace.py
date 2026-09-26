"""Read-only summaries and panels for the morphospace publication figure.

Reads the tables `morphospace integrate` wrote into the backend database
(packages/morphospace). Nothing here recomputes the morphospaces: the figure
shows exactly what the site serves, from one identified run.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from analyses.helpers.publication import (
    AnalysisError,
    Settings,
    connect,
    table,
)

SIDES = ("dorsal", "ventral")
# The same five ColorBrewer Dark2 slots, in the same order, as the site's
# morphospace plot (`--ms-series-*` in src/app/globals.css): slots 1-4 and 7.
# Dark2's green and yellow fall under 3:1 against white and are skipped. The
# five cannot all be told apart under colour-vision deficiency, so each group
# also keeps the site's marker shape.
GROUP_COLORS = ("#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#a6761d")
GROUP_MARKERS = ("o", "s", "^", "D", "v")
# Grey context at 3:1 against white, like the site's muted points.
OTHER_COLOR = "#a29090"
LINK_COLOR = "#8b7474"


def morphospace_summaries(
    settings: Settings,
    *,
    scope_rank: str = "all",
    scope_key: str = "all",
) -> dict[str, pd.DataFrame]:
    """Every table the figure draws, one per panel plus the scope it is set in."""
    with connect(settings) as connection:
        scopes = table(
            connection,
            settings,
            "morphospace_scope",
            (
                "scope_rank",
                "scope_key",
                "scope_name",
                "parent_family",
                "n_species",
                "n_species_both",
                "explained_pc1",
                "explained_pc2",
                "dv_mantel_n",
                "dv_mantel_r",
                "dv_mantel_p",
                "run_id",
            ),
        )
        points = table(
            connection,
            settings,
            "morphospace_points",
            (
                "scope_rank",
                "scope_key",
                "accepted_species",
                "genus_key",
                "family_key",
                "side",
                "pc1",
                "pc2",
            ),
        )
        species = table(
            connection,
            settings,
            "morphospace_species",
            (
                "accepted_species",
                "genus_key",
                "family_name",
                "dorsal_dispersion",
                "ventral_dispersion",
                "dv_divergence",
            ),
        )
        disparity = table(
            connection,
            settings,
            "morphospace_disparity",
            (
                "scope_rank",
                "scope_key",
                "side",
                "n_species",
                "rarefied_mean",
                "rarefied_low",
                "rarefied_high",
            ),
        )
        scope = connection.execute(
            f"SELECT * FROM {scopes} WHERE scope_rank = ? AND scope_key = ?",
            [scope_rank, scope_key],
        ).df()
        if scope.empty:
            raise AnalysisError(
                f"No morphospace for {scope_rank} {scope_key!r}; run morphospace integrate."
            )
        run_ids = connection.execute(f"SELECT DISTINCT run_id FROM {scopes}").fetchall()
        if len(run_ids) != 1:
            raise AnalysisError("The morphospace tables mix runs; integrate one run.")
        scope_points = connection.execute(
            f"""
            SELECT accepted_species, genus_key, family_key, side, pc1, pc2
            FROM {points} WHERE scope_rank = ? AND scope_key = ?
            ORDER BY accepted_species, side
            """,
            [scope_rank, scope_key],
        ).df()
        genus_disparity = connection.execute(
            f"""
            SELECT s.scope_key AS genus, s.scope_name, s.parent_family, s.n_species,
                   d.side, d.n_species AS side_species, d.rarefied_mean,
                   d.rarefied_low, d.rarefied_high
            FROM {scopes} s
            JOIN {disparity} d USING (scope_rank, scope_key)
            WHERE s.scope_rank = 'genus' AND d.rarefied_mean IS NOT NULL
            """
        ).df()
        integration = connection.execute(
            f"""
            SELECT scope_key AS genus, scope_name, parent_family, n_species,
                   dv_mantel_n, dv_mantel_r, dv_mantel_p
            FROM {scopes}
            WHERE scope_rank = 'genus' AND dv_mantel_r IS NOT NULL
            ORDER BY dv_mantel_n DESC
            """
        ).df()
        variation = connection.execute(
            f"""
            SELECT accepted_species, genus_key, family_name, dorsal_dispersion,
                   ventral_dispersion,
                   (dorsal_dispersion + ventral_dispersion) / 2 AS mean_dispersion,
                   dv_divergence
            FROM {species}
            WHERE dv_divergence IS NOT NULL
            """
        ).df()
    wide = genus_disparity.pivot_table(
        index=["genus", "scope_name", "parent_family", "n_species"],
        columns="side",
        values=["rarefied_mean", "rarefied_low", "rarefied_high"],
    )
    wide.columns = [f"{side}_{value.removeprefix('rarefied_')}" for value, side in wide.columns]
    wide = wide.reset_index().dropna(subset=["dorsal_mean", "ventral_mean"])
    return {
        "scope": scope,
        "points": scope_points,
        "disparity": wide,
        "integration": integration,
        "species": variation,
    }


def group_colors(labels: pd.Series, top: int = len(GROUP_COLORS)) -> dict:
    """Colour and marker for the `top` most species-rich groups; the rest are grey.

    More categories than the palette holds cannot be told apart, so the rest
    fold into one "Other" rather than cycling colours.
    """
    top = min(top, len(GROUP_COLORS))
    leaders = list(labels.dropna().value_counts().index[:top])
    return {
        leader: (GROUP_COLORS[slot], GROUP_MARKERS[slot]) for slot, leader in enumerate(leaders)
    }


def morphospace_panel(
    ax, points: pd.DataFrame, scope: pd.Series, *, top: int = len(GROUP_COLORS)
) -> dict:
    """Species centroids on the shared dorso-ventral PC1 × PC2.

    Dorsal filled, ventral hollow, a thin segment joining the two sides of each
    species in a coloured group. Colour follows the family in the
    whole-collection scope and the genus inside a family.
    """
    group = "family_key" if scope["scope_rank"] == "all" else "genus_key"
    colors = group_colors(points.loc[points["side"] == "dorsal", group], top=top)
    focus = points[group].isin(colors.keys())
    for side, filled in (("dorsal", True), ("ventral", False)):
        rows = (points["side"] == side) & ~focus
        ax.scatter(
            points.loc[rows, "pc1"],
            points.loc[rows, "pc2"],
            s=6,
            facecolors=OTHER_COLOR if filled else "none",
            edgecolors=OTHER_COLOR,
            linewidths=0.6,
            alpha=0.35,
            rasterized=True,
            zorder=1,
        )
        for key, (c, marker) in colors.items():
            rows = (points["side"] == side) & (points[group] == key)
            ax.scatter(
                points.loc[rows, "pc1"],
                points.loc[rows, "pc2"],
                s=12,
                marker=marker,
                facecolors=c if filled else "none",
                edgecolors=c,
                linewidths=0.7,
                alpha=0.85,
                rasterized=True,
                zorder=3,
            )
    paired = (
        points.loc[focus]
        .pivot_table(index="accepted_species", columns="side", values=["pc1", "pc2"])
        .dropna()
    )
    if len(paired):
        segments = np.stack(
            [
                paired[[("pc1", "dorsal"), ("pc2", "dorsal")]].to_numpy(),
                paired[[("pc1", "ventral"), ("pc2", "ventral")]].to_numpy(),
            ],
            axis=1,
        )
        from matplotlib.collections import LineCollection

        ax.add_collection(
            LineCollection(segments, colors=LINK_COLOR, linewidths=0.3, alpha=0.4, zorder=2)
        )
    ax.set_xlabel(f"PC1 ({scope['explained_pc1'] * 100:.1f}%)")
    ax.set_ylabel(f"PC2 ({scope['explained_pc2'] * 100:.1f}%)")
    handles = [
        plt.Line2D([], [], marker=m, linestyle="", color=c, label=str(k).capitalize())
        for k, (c, m) in colors.items()
    ]
    handles += [
        plt.Line2D([], [], marker="o", linestyle="", color=OTHER_COLOR, label="Other"),
        plt.Line2D([], [], marker="o", linestyle="", color="black", label="Dorsal"),
        plt.Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markerfacecolor="none",
            color="black",
            label="Ventral",
        ),
    ]
    ax.legend(handles=handles, loc="best", fontsize=7, frameon=False, ncols=2)
    sns.despine(ax=ax)
    return colors


def disparity_panel(ax, frame: pd.DataFrame) -> None:
    """Genus rarefied disparity, dorsal against ventral, with 95% intervals and 1:1."""
    color = GROUP_COLORS[0]
    ax.errorbar(
        frame["dorsal_mean"],
        frame["ventral_mean"],
        xerr=[
            frame["dorsal_mean"] - frame["dorsal_low"],
            frame["dorsal_high"] - frame["dorsal_mean"],
        ],
        yerr=[
            frame["ventral_mean"] - frame["ventral_low"],
            frame["ventral_high"] - frame["ventral_mean"],
        ],
        fmt="o",
        markersize=3,
        color=color,
        ecolor=color,
        elinewidth=0.4,
        alpha=0.6,
    )
    low = float(np.nanmin(frame[["dorsal_low", "ventral_low"]].to_numpy()))
    high = float(np.nanmax(frame[["dorsal_high", "ventral_high"]].to_numpy()))
    ax.plot([low, high], [low, high], linestyle="--", color=LINK_COLOR, linewidth=0.8)
    ax.set_xlim(low, high)
    ax.set_ylim(low, high)
    ax.set_aspect("equal")
    ax.set_xlabel("Dorsal disparity (rarefied)")
    ax.set_ylabel("Ventral disparity (rarefied)")
    sns.despine(ax=ax)


def integration_panel(ax, frame: pd.DataFrame, reference: float | None) -> None:
    """Genus Mantel r against the species seen from both sides."""
    color = GROUP_COLORS[0]
    significant = frame["dv_mantel_p"].notna() & (frame["dv_mantel_p"] < 0.05)
    ax.scatter(
        frame.loc[significant, "dv_mantel_n"],
        frame.loc[significant, "dv_mantel_r"],
        s=12,
        color=color,
        label="p < 0.05",
    )
    ax.scatter(
        frame.loc[~significant, "dv_mantel_n"],
        frame.loc[~significant, "dv_mantel_r"],
        s=12,
        facecolors="none",
        edgecolors=color,
        label="p ≥ 0.05",
    )
    if reference is not None and np.isfinite(reference):
        ax.axhline(reference, linestyle="--", color=LINK_COLOR, linewidth=0.8)
        ax.annotate(
            f"scope r = {reference:.2f}",
            (1, reference),
            xycoords=("axes fraction", "data"),
            ha="right",
            va="bottom",
            fontsize=7,
            color="#555555",
        )
    ax.set_xscale("log")
    ax.set_xlabel("Species seen from both sides")
    ax.set_ylabel("Dorso-ventral integration (Mantel r, −1 to 1)")
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    sns.despine(ax=ax)


def variation_panel(ax, frame: pd.DataFrame) -> None:
    """Intraspecific dispersion against dorso-ventral divergence, per species."""
    color = GROUP_COLORS[0]
    ax.scatter(
        frame["mean_dispersion"],
        frame["dv_divergence"],
        s=3,
        alpha=0.25,
        color=color,
        rasterized=True,
    )
    if len(frame) >= 20:
        sns.kdeplot(
            data=frame,
            x="mean_dispersion",
            y="dv_divergence",
            levels=5,
            color="black",
            linewidths=0.5,
            ax=ax,
        )
    rho = frame[["mean_dispersion", "dv_divergence"]].corr(method="spearman").iloc[0, 1]
    ax.annotate(
        f"Spearman ρ = {rho:.2f}",
        (0.98, 0.98),
        xycoords="axes fraction",
        ha="right",
        va="top",
        fontsize=7,
    )
    ax.set_xlabel("Intraspecific dispersion (mean of sides)")
    ax.set_ylabel("Dorso-ventral divergence")
    sns.despine(ax=ax)
