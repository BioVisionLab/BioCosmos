from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from geoharmonize.config import (
    merge_coordinate_config,
    parse_coordinate_mapping_options,
    template_text,
)
from geoharmonize.models import ProjectConfig


def test_packaged_template_is_valid() -> None:
    project = ProjectConfig.model_validate(tomllib.loads(template_text()))
    assert project.coordinates.tile_size == 5.0


def test_unknown_toml_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate({"coordinates": {"unknown": 1}})


def test_other_tools_tables_are_ignored() -> None:
    """One shared file may carry colharmonize's tables without breaking this tool."""
    project = ProjectConfig.model_validate(
        {"matching": {"top_k": 3}, "coordinates": {"tile_size": 10}}
    )
    assert project.coordinates.tile_size == 10


def test_taxonomy_keys_in_run_table_are_ignored(tmp_path: Path) -> None:
    """`[run]` is owned by colharmonize; its extra keys must not break this tool."""
    occurrence = tmp_path / "source.duckdb"
    occurrence.touch()
    project = ProjectConfig.model_validate(
        {
            "run": {
                "db": str(occurrence),
                "table": "occurrence",
                "col": "/path/to/NameUsage.tsv",
                "plot_palette": "Set2",
                "csv": True,
            }
        }
    )
    assert project.run.db == occurrence


def test_cli_mapping_validation() -> None:
    assert parse_coordinate_mapping_options(["latitude=lat", "longitude=lon"]) == {
        "latitude": "lat",
        "longitude": "lon",
    }


def test_coordinate_config_falls_back_to_shared_run_values(tmp_path: Path) -> None:
    occurrence = tmp_path / "source.duckdb"
    occurrence.touch()
    gadm = tmp_path / "gadm.gpkg"
    gadm.touch()
    project = ProjectConfig.model_validate(
        {
            "run": {
                "db": str(occurrence),
                "table": "occurrence",
                "col": str(tmp_path / "NameUsage.tsv"),
                "output": str(tmp_path / "configured"),
            },
            "coordinates": {"gadm": str(gadm), "tile_size": 10},
        }
    )
    effective = merge_coordinate_config(
        project,
        overrides={"tile_size": 2.5},
        mapping_values=["latitude=lat", "longitude=lon"],
    )
    assert effective.db == occurrence
    assert effective.table == "occurrence"
    assert effective.output == tmp_path / "configured"
    assert effective.gadm == gadm
    assert effective.tile_size == 2.5
