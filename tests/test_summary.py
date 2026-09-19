from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from colharmonize.summary import (
    SummaryService,
    _spread_label_positions,
    _status_label,
    resolve_palette_name,
)


def test_palette_names_are_case_insensitive() -> None:
    assert resolve_palette_name("dark2") == "Dark2"
    assert resolve_palette_name("colorblind") == "colorblind"


def test_unknown_palette_has_clear_error() -> None:
    with pytest.raises(ValueError, match="Unknown Seaborn palette"):
        resolve_palette_name("not-a-real-palette")


def test_status_label_combines_name_count_and_percentage() -> None:
    assert _status_label("MATCHED", 7_000, 10_000) == "Matched — 7,000 (70.0%)"


def test_pie_label_positions_are_spread_and_bounded() -> None:
    positions = _spread_label_positions([(0, 0.9), (1, 0.91), (2, 0.92)])
    ordered = [positions[index] for index in range(3)]
    assert ordered[1] - ordered[0] >= 0.22 - 1e-9
    assert ordered[2] - ordered[1] >= 0.22 - 1e-9
    assert min(ordered) >= -0.95
    assert max(ordered) <= 0.95


def test_empty_plot_uses_fallback(tmp_path: Path) -> None:
    database = tmp_path / "empty.duckdb"
    connection = duckdb.connect(str(database))
    try:
        connection.execute(
            "CREATE TABLE taxonomy_matches (update_status VARCHAR, match_method VARCHAR)"
        )
    finally:
        connection.close()

    result = SummaryService().export_plot(database, tmp_path, force=False)

    assert result.is_file()
