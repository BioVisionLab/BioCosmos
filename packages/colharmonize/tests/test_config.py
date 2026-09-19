from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from colharmonize.config import (
    merge_coordinate_config,
    merge_run_config,
    parse_coordinate_mapping_options,
    parse_mapping_options,
    template_text,
)
from colharmonize.models import ProjectConfig


def test_packaged_template_is_valid() -> None:
    project = ProjectConfig.model_validate(tomllib.loads(template_text()))
    assert project.run.plot_palette == "Dark2"
    assert project.coordinates.tile_size == 5.0


def test_unknown_toml_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate({"matching": {"unknown": 1}})


def test_cli_mapping_validation() -> None:
    assert parse_mapping_options(["scientific_name=species"]) == {"scientific_name": "species"}
    assert parse_coordinate_mapping_options(["latitude=lat", "longitude=lon"]) == {
        "latitude": "lat",
        "longitude": "lon",
    }


def test_cli_values_override_toml(tmp_path: Path) -> None:
    occurrence = tmp_path / "source.duckdb"
    occurrence.touch()
    col = tmp_path / "NameUsage.tsv"
    col.touch()
    project = ProjectConfig.model_validate(
        {
            "run": {
                "db": str(occurrence),
                "table": "occurrence",
                "col": str(col),
                "output": str(tmp_path / "configured"),
                "plot_palette": "Set2",
            },
            "matching": {"top_k": 3},
        }
    )
    effective = merge_run_config(
        project,
        overrides={
            "output": tmp_path / "overridden",
            "plot_palette": "Dark2",
            "top_k": 7,
        },
        mapping_values=None,
    )
    assert effective.output == tmp_path / "overridden"
    assert effective.plot_palette == "Dark2"
    assert effective.matching.top_k == 7


def test_coordinate_config_falls_back_to_shared_run_values(tmp_path: Path) -> None:
    occurrence = tmp_path / "source.duckdb"
    occurrence.touch()
    col = tmp_path / "NameUsage.tsv"
    col.touch()
    gadm = tmp_path / "gadm.gpkg"
    gadm.touch()
    project = ProjectConfig.model_validate(
        {
            "run": {
                "db": str(occurrence),
                "table": "occurrence",
                "col": str(col),
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
