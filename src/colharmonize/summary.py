"""Summary table and optional human-readable artifacts."""

from __future__ import annotations

import os
import uuid
from math import cos, radians, sin
from pathlib import Path

import duckdb

from colharmonize.errors import OutputError
from colharmonize.identifiers import quote_literal


def resolve_palette_name(palette: str) -> str:
    """Return a valid Seaborn palette name, matching named palettes case-insensitively."""
    requested = palette.strip()
    if not requested:
        raise ValueError("Plot palette cannot be empty")

    import matplotlib

    matplotlib.use("Agg")
    import seaborn as sns
    from matplotlib import colormaps

    try:
        sns.color_palette(requested)
        return requested
    except (KeyError, ValueError) as original_error:
        seaborn_names = getattr(sns.palettes, "SEABORN_PALETTES", {})
        known_names = {str(name) for name in colormaps}
        known_names.update(str(name) for name in seaborn_names)
        canonical = next(
            (name for name in known_names if name.casefold() == requested.casefold()),
            None,
        )
        if canonical is None:
            raise ValueError(
                f"Unknown Seaborn palette {palette!r}; "
                "choose a named palette such as Dark2, Set2, or colorblind"
            ) from original_error
        sns.color_palette(canonical)
        return canonical


def _status_label(status: str, count: int, total: int) -> str:
    percentage = count / total if total else 0.0
    name = status.replace("_", " ").title()
    return f"{name} — {count:,} ({percentage:.1%})"


def _spread_label_positions(
    values: list[tuple[int, float]],
    *,
    minimum_gap: float = 0.22,
    lower: float = -0.95,
    upper: float = 0.95,
) -> dict[int, float]:
    """Spread label positions vertically while preserving their order."""
    if not values:
        return {}
    ordered = sorted(values, key=lambda item: item[1])
    adjusted = [[index, max(lower, position)] for index, position in ordered]
    for position in range(1, len(adjusted)):
        adjusted[position][1] = max(adjusted[position][1], adjusted[position - 1][1] + minimum_gap)
    overflow = adjusted[-1][1] - upper
    if overflow > 0:
        for item in adjusted:
            item[1] -= overflow
    for position in range(len(adjusted) - 2, -1, -1):
        adjusted[position][1] = min(adjusted[position][1], adjusted[position + 1][1] - minimum_gap)
    underflow = lower - adjusted[0][1]
    if underflow > 0:
        for item in adjusted:
            item[1] += underflow
    return {int(index): float(position) for index, position in adjusted}


class SummaryService:
    """Regenerate metrics, CSV, and plots from a completed output database."""

    def refresh_metrics(self, connection: duckdb.DuckDBPyConnection) -> None:
        connection.execute(
            """
            CREATE OR REPLACE TABLE summary_metrics AS
            WITH metrics AS (
                SELECT 'update_status' AS metric, update_status AS value, count(*)::BIGINT AS count
                FROM taxonomy_matches GROUP BY update_status
                UNION ALL
                SELECT 'match_method', match_method, count(*)::BIGINT
                FROM taxonomy_matches GROUP BY match_method
                UNION ALL
                SELECT 'total', 'input_taxa', count(*)::BIGINT FROM taxonomy_matches
            )
            SELECT metric, value, count,
                round(count * 100.0 / sum(count) OVER (PARTITION BY metric), 2) AS percentage
            FROM metrics
            ORDER BY metric, value
            """
        )

    def export_csv(self, database: Path, output_dir: Path, *, force: bool) -> Path:
        destination = output_dir / "taxonomy_summary.csv"
        if destination.exists() and not force:
            raise OutputError(f"CSV already exists: {destination}")
        temporary = output_dir / f".taxonomy_summary.{uuid.uuid4().hex}.csv"
        connection = duckdb.connect(str(database), read_only=True)
        try:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info('taxonomy_matches')").fetchall()
            }
            alternatives = (
                "alternative_matches" if "alternative_matches" in columns else "runner_up_name"
            )
            rank = "accepted_rank" if "accepted_rank" in columns else "NULL::VARCHAR"
            connection.execute(
                f"""
                COPY (
                    SELECT
                        input_taxon_key,
                        original_scientific_name,
                        original_family,
                        accepted_name,
                        accepted_id,
                        match_method,
                        match_score,
                        update_status,
                        candidate_count,
                        {rank} AS accepted_rank,
                        {alternatives} AS alternative_matches,
                        score_margin
                    FROM taxonomy_matches
                    ORDER BY input_taxon_key
                ) TO {quote_literal(str(temporary))} (HEADER, FORMAT CSV)
                """
            )
            os.replace(temporary, destination)
        finally:
            connection.close()
            temporary.unlink(missing_ok=True)
        return destination

    def export_plot(
        self,
        database: Path,
        output_dir: Path,
        *,
        force: bool,
        palette: str = "Dark2",
    ) -> Path:
        palette = resolve_palette_name(palette)
        destination = output_dir / "taxonomy_match_summary.png"
        if destination.exists() and not force:
            raise OutputError(f"Plot already exists: {destination}")
        temporary = output_dir / f".taxonomy_match_summary.{uuid.uuid4().hex}.png"
        connection = duckdb.connect(str(database), read_only=True)
        try:
            status_rows = connection.execute(
                """
                SELECT update_status, count(*)
                FROM taxonomy_matches
                GROUP BY update_status
                ORDER BY CASE update_status
                    WHEN 'MATCHED' THEN 1 WHEN 'AMBIGUOUS' THEN 2 ELSE 3 END
                """
            ).fetchall()
            method_rows = connection.execute(
                """
                SELECT match_method, count(*)
                FROM taxonomy_matches
                WHERE update_status = 'MATCHED'
                GROUP BY match_method
                ORDER BY count(*) DESC, match_method
                """
            ).fetchall()
        finally:
            connection.close()

        import matplotlib

        matplotlib.use("Agg")
        import seaborn as sns
        from matplotlib import pyplot as plt

        sns.set_theme(style="whitegrid", context="notebook")
        status_labels = [str(row[0]) for row in status_rows]
        status_counts = [int(row[1]) for row in status_rows]
        status_total = sum(status_counts)
        status_palette = sns.color_palette(palette, n_colors=3)
        status_colors = {
            "MATCHED": status_palette[0],
            "AMBIGUOUS": status_palette[1],
            "UNMATCHED": status_palette[2],
        }

        figure, (status_axis, method_axis) = plt.subplots(
            1,
            2,
            figsize=(14, 6.5),
            gridspec_kw={"width_ratios": (0.9, 1.25)},
        )

        if status_total:
            wedges, _ = status_axis.pie(
                status_counts,
                colors=[status_colors.get(label, status_palette[0]) for label in status_labels],
                startangle=90,
                counterclock=False,
                wedgeprops={"edgecolor": "white", "linewidth": 1.5},
            )
            callouts: dict[int, list[tuple[int, float]]] = {-1: [], 1: []}
            anchors: dict[int, tuple[float, float]] = {}
            for index, wedge in enumerate(wedges):
                angle = radians((wedge.theta1 + wedge.theta2) / 2)
                anchor = (cos(angle), sin(angle))
                side = 1 if anchor[0] >= 0 else -1
                anchors[index] = anchor
                callouts[side].append((index, anchor[1]))

            label_positions = {
                **_spread_label_positions(callouts[-1]),
                **_spread_label_positions(callouts[1]),
            }
            pie_labels = [
                _status_label(label, count, status_total)
                for label, count in zip(status_labels, status_counts, strict=True)
            ]
            for index, label in enumerate(pie_labels):
                anchor_x, anchor_y = anchors[index]
                side = 1 if anchor_x >= 0 else -1
                status_axis.annotate(
                    label,
                    xy=(0.94 * anchor_x, 0.94 * anchor_y),
                    xytext=(1.17 * side, label_positions[index]),
                    ha="left" if side > 0 else "right",
                    va="center",
                    fontsize=9,
                    arrowprops={
                        "arrowstyle": "-",
                        "color": "#666666",
                        "connectionstyle": "arc3,rad=0.08",
                    },
                )
            status_axis.set_xlim(-1.5, 1.5)
            status_axis.set_ylim(-1.2, 1.2)
        else:
            status_axis.text(0.5, 0.5, "No input taxa", ha="center", va="center")
            status_axis.set_axis_off()
        status_axis.set_title("Update status", fontweight="bold", pad=14)

        method_labels = [str(row[0]).replace("_", " ").title() for row in method_rows]
        method_counts = [int(row[1]) for row in method_rows]
        method_total = sum(method_counts)
        method_palette = sns.color_palette(palette, n_colors=max(len(method_labels), 1))
        bars = method_axis.barh(method_labels, method_counts, color=method_palette)
        method_axis.invert_yaxis()
        value_labels = [
            f"{count:,} ({count / method_total:.1%})" if method_total else f"{count:,}"
            for count in method_counts
        ]
        method_axis.bar_label(bars, labels=value_labels, padding=5, fontsize=9)
        if method_counts:
            method_axis.set_xlim(0, max(method_counts) * 1.3)
        method_axis.set_title("How matched taxa were resolved", fontweight="bold", pad=14)
        method_axis.set_xlabel("Distinct input taxa")
        method_axis.set_ylabel("Match method")
        method_axis.spines[["top", "right", "left"]].set_visible(False)
        method_axis.grid(axis="x", alpha=0.25)
        method_axis.grid(axis="y", visible=False)

        figure.suptitle("Taxonomy match summary", fontsize=16, fontweight="bold")
        figure.tight_layout(rect=(0, 0.02, 1, 0.95))
        figure.savefig(temporary, dpi=180)
        plt.close(figure)
        os.replace(temporary, destination)
        return destination
