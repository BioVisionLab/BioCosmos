"""TOML loading and command-line override handling for coordinate validation."""

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

from geoharmonize.models import (
    CoordinateColumnMappings,
    EffectiveCoordinateRunConfig,
    ProjectConfig,
)

# Settings coordinate validation inherits from ``[run]`` when its own table omits them.
INHERITED_FROM_RUN = ("db", "table", "output", "reports_dir")


def load_project_config(path: Path | None) -> ProjectConfig:
    return _load_project_config(path, ProjectConfig)


def parse_coordinate_mapping_options(values: list[str] | None) -> dict[str, str]:
    return _parse_mapping_options(
        values, CoordinateColumnMappings, label="coordinate column mapping"
    )


def merge_coordinate_config(
    project: ProjectConfig,
    *,
    overrides: dict[str, Any],
    mapping_values: list[str] | None,
) -> EffectiveCoordinateRunConfig:
    """Resolve coordinate-validation configuration with CLI values taking precedence."""
    coordinate_data = project.coordinates.model_dump()
    for shared in INHERITED_FROM_RUN:
        if coordinate_data.get(shared) is None:
            coordinate_data[shared] = getattr(project.run, shared)
    coordinate_data = apply_overrides(coordinate_data, overrides)

    column_data = project.coordinate_columns.model_dump()
    column_data.update(parse_coordinate_mapping_options(mapping_values))
    require_settings(coordinate_data, ("db", "table", "gadm", "output"), label="coordinate")

    payload = {
        **{
            key: coordinate_data[key]
            for key in EffectiveCoordinateRunConfig.model_fields
            if key in coordinate_data
        },
        "columns": column_data,
    }
    try:
        return EffectiveCoordinateRunConfig.model_validate(payload)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid coordinate configuration: {exc}") from exc


def template_text() -> str:
    return resources.files("geoharmonize.resources").joinpath("config.template.toml").read_text()


def write_template(output: str, *, force: bool) -> Path | None:
    return _write_template(template_text(), output, force=force)
