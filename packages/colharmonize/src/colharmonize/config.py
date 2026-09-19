"""TOML loading and command-line override handling for taxonomy matching."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

from harmonize_core.config import (
    apply_overrides,
    require_settings,
)
from harmonize_core.config import (
    load_project_config as _load_project_config,
)
from harmonize_core.config import (
    parse_mapping_options as _parse_mapping_options,
)
from harmonize_core.config import write_template as _write_template
from harmonize_core.errors import ConfigurationError
from pydantic import ValidationError

from colharmonize.models import ColumnMappings, EffectiveRunConfig, ProjectConfig

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "colharmonize"


def load_project_config(path: Path | None) -> ProjectConfig:
    return _load_project_config(path, ProjectConfig)


def parse_mapping_options(values: list[str] | None) -> dict[str, str]:
    return _parse_mapping_options(values, ColumnMappings, label="column mapping")


def merge_run_config(
    project: ProjectConfig,
    *,
    overrides: dict[str, Any],
    mapping_values: list[str] | None,
) -> EffectiveRunConfig:
    run_data = apply_overrides(project.run.model_dump(), overrides)

    column_data = project.columns.model_dump(by_alias=True)
    column_data.update(parse_mapping_options(mapping_values))
    matching_data = project.matching.model_dump()
    for key in tuple(matching_data):
        if overrides.get(key) is not None:
            matching_data[key] = overrides[key]

    require_settings(run_data, ("db", "table", "col", "output"), label="run")
    if run_data.get("cache_dir") is None:
        run_data["cache_dir"] = DEFAULT_CACHE_DIR

    payload = {
        **{key: run_data[key] for key in EffectiveRunConfig.model_fields if key in run_data},
        "columns": column_data,
        "matching": matching_data,
    }
    try:
        return EffectiveRunConfig.model_validate(payload)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid run configuration: {exc}") from exc


def template_text() -> str:
    return resources.files("colharmonize.resources").joinpath("config.template.toml").read_text()


def write_template(output: str, *, force: bool) -> Path | None:
    return _write_template(template_text(), output, force=force)
