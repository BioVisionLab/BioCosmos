from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from colharmonize.config import merge_run_config, parse_mapping_options, template_text
from colharmonize.models import ProjectConfig


def test_packaged_template_is_valid() -> None:
    project = ProjectConfig.model_validate(tomllib.loads(template_text()))
    assert project.run.plot_palette == "Dark2"


def test_unknown_toml_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate({"matching": {"unknown": 1}})


def test_other_tools_tables_are_ignored() -> None:
    """One shared file may carry geoharmonize's tables without breaking this tool."""
    project = ProjectConfig.model_validate(
        {"matching": {"top_k": 3}, "coordinates": {"tile_size": 10}}
    )
    assert project.matching.top_k == 3


def test_cli_mapping_validation() -> None:
    assert parse_mapping_options(["scientific_name=species"]) == {"scientific_name": "species"}


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
