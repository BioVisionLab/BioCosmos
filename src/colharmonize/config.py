"""TOML loading and command-line override handling."""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from colharmonize.errors import ConfigurationError, OutputError
from colharmonize.models import ColumnMappings, EffectiveRunConfig, ProjectConfig


def load_project_config(path: Path | None) -> ProjectConfig:
    if path is None:
        return ProjectConfig()
    if not path.is_file():
        raise ConfigurationError(f"Configuration file does not exist: {path}")
    try:
        with path.open("rb") as stream:
            return ProjectConfig.model_validate(tomllib.load(stream))
    except (tomllib.TOMLDecodeError, ValidationError) as exc:
        raise ConfigurationError(f"Invalid configuration in {path}: {exc}") from exc


def parse_mapping_options(values: list[str] | None) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for value in values or []:
        logical, separator, physical = value.partition("=")
        if not separator or not logical.strip() or not physical.strip():
            raise ConfigurationError(f"Invalid mapping {value!r}; expected FIELD=COLUMN")
        mappings[logical.strip()] = physical.strip()
    try:
        return ColumnMappings.model_validate(mappings).as_logical_dict()
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid column mapping: {exc}") from exc


def merge_run_config(
    project: ProjectConfig,
    *,
    overrides: dict[str, Any],
    mapping_values: list[str] | None,
) -> EffectiveRunConfig:
    run_data = project.run.model_dump()
    for key, value in overrides.items():
        if value is not None:
            run_data[key] = value

    column_data = project.columns.model_dump(by_alias=True)
    column_data.update(parse_mapping_options(mapping_values))
    matching_data = project.matching.model_dump()
    for key in tuple(matching_data):
        if overrides.get(key) is not None:
            matching_data[key] = overrides[key]

    missing = [key for key in ("db", "table", "col", "output") if run_data.get(key) is None]
    if missing:
        raise ConfigurationError(
            "Missing required run settings: "
            + ", ".join(missing)
            + ". Supply CLI options or TOML values."
        )
    if run_data.get("cache_dir") is None:
        run_data["cache_dir"] = Path.home() / ".cache" / "colharmonize"

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
    text = template_text()
    if output == "-":
        print(text, end="")
        return None
    path = Path(output)
    if path.exists() and not force:
        raise OutputError(f"Refusing to overwrite existing configuration: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
