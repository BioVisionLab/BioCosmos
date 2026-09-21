"""Shared TOML loading and command-line override handling."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from harmonize_core.errors import ConfigurationError, OutputError


def load_project_config[ConfigT: BaseModel](path: Path | None, model: type[ConfigT]) -> ConfigT:
    """Load one tool's view of a shared configuration file."""
    if path is None:
        return model()
    if not path.is_file():
        raise ConfigurationError(f"Configuration file does not exist: {path}")
    try:
        with path.open("rb") as stream:
            return model.model_validate(tomllib.load(stream))
    except (tomllib.TOMLDecodeError, ValidationError) as exc:
        raise ConfigurationError(f"Invalid configuration in {path}: {exc}") from exc


def parse_mapping_options[MappingT: BaseModel](
    values: list[str] | None,
    model: type[MappingT],
    *,
    label: str = "column mapping",
) -> dict[str, str]:
    """Parse repeated ``FIELD=COLUMN`` options into a validated logical mapping."""
    mappings: dict[str, str] = {}
    for value in values or []:
        logical, separator, physical = value.partition("=")
        if not separator or not logical.strip() or not physical.strip():
            raise ConfigurationError(f"Invalid mapping {value!r}; expected FIELD=COLUMN")
        mappings[logical.strip()] = physical.strip()
    try:
        validated = model.model_validate(mappings)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid {label}: {exc}") from exc
    return validated.as_logical_dict()  # type: ignore[attr-defined]


def apply_overrides(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Apply non-``None`` command-line values over configuration values."""
    for key, value in overrides.items():
        if value is not None:
            base[key] = value
    return base


def require_settings(data: dict[str, Any], required: tuple[str, ...], *, label: str) -> None:
    """Raise when a required setting was supplied by neither the CLI nor TOML."""
    missing = [key for key in required if data.get(key) is None]
    if missing:
        raise ConfigurationError(
            f"Missing required {label} settings: "
            + ", ".join(missing)
            + ". Supply CLI options or TOML values."
        )


def write_template(text: str, output: str, *, force: bool) -> Path | None:
    """Write a configuration template, or print it when ``output`` is ``-``."""
    if output == "-":
        print(text, end="")
        return None
    path = Path(output)
    if path.exists() and not force:
        raise OutputError(f"Refusing to overwrite existing configuration: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
