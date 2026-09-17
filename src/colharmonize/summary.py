"""Summary table and optional human-readable artifacts."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import duckdb

from colharmonize.errors import OutputError
from colharmonize.identifiers import quote_literal


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
                        runner_up_name,
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

    def export_plot(self, database: Path, output_dir: Path, *, force: bool) -> Path:
        destination = output_dir / "taxonomy_match_summary.png"
        if destination.exists() and not force:
            raise OutputError(f"Plot already exists: {destination}")
        temporary = output_dir / f".taxonomy_match_summary.{uuid.uuid4().hex}.png"
        connection = duckdb.connect(str(database), read_only=True)
        try:
            rows = connection.execute(
                """
                SELECT update_status, count(*)
                FROM taxonomy_matches
                GROUP BY update_status
                ORDER BY CASE update_status
                    WHEN 'MATCHED' THEN 1 WHEN 'AMBIGUOUS' THEN 2 ELSE 3 END
                """
            ).fetchall()
        finally:
            connection.close()

        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        labels = [row[0] for row in rows]
        counts = [row[1] for row in rows]
        colors = {"MATCHED": "#2E8B57", "AMBIGUOUS": "#E69F00", "UNMATCHED": "#C44E52"}
        figure, axis = plt.subplots(figsize=(8, 5))
        bars = axis.bar(labels, counts, color=[colors.get(label, "#4C78A8") for label in labels])
        axis.set_title("Distinct input taxa by update status")
        axis.set_xlabel("Update status")
        axis.set_ylabel("Distinct input taxa")
        axis.bar_label(bars, padding=3)
        figure.tight_layout()
        figure.savefig(temporary, dpi=180)
        plt.close(figure)
        os.replace(temporary, destination)
        return destination
