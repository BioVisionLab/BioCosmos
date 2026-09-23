"""Hand-checked institution entries that take precedence over the registry.

For codes the registries cannot settle: absent from GRSciColl, or shared by
several institutions there, with a publisher name that does not spell out the
code. The bundled file ships with the package; a caller may layer its own on
top.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Mapping
from importlib import resources
from pathlib import Path

from harmonize_core.errors import ConfigurationError
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

BUNDLED_OVERRIDES = "overrides.toml"


class Override(BaseModel):
    """One curated code.

    `use_publisher` takes the name and homepage from the GBIF publisher of the
    code's datasets -- for a code whose publisher *is* the holding institution
    but whose name does not spell the code out. `name` and `homepage`, when
    given, win over the publisher's.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str | None = None
    homepage: str | None = None
    country: str | None = None
    use_publisher: bool = False

    @model_validator(mode="after")
    def _has_a_name_source(self) -> Override:
        if not self.name and not self.use_publisher:
            raise ValueError("an override needs a name or use_publisher = true")
        if self.homepage and not self.homepage.startswith(("http://", "https://")):
            raise ValueError(f"homepage must be an http(s) URL, got {self.homepage!r}")
        return self


def _parse(text: str, origin: str) -> dict[str, Override]:
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigurationError(f"{origin}: {error}") from error
    entries = document.get("institutions", {})
    overrides: dict[str, Override] = {}
    for code, entry in entries.items():
        try:
            overrides[code.strip()] = Override.model_validate(entry)
        except ValidationError as error:
            raise ConfigurationError(f"{origin}: institution {code!r}: {error}") from error
    return overrides


def load_overrides(extra: Path | None = None, *, bundled: bool = True) -> dict[str, Override]:
    """The bundled overrides, with `extra` layered on top when given."""
    overrides: dict[str, Override] = {}
    if bundled:
        text = (
            resources.files("instharmonize.resources")
            .joinpath(BUNDLED_OVERRIDES)
            .read_text(encoding="utf-8")
        )
        overrides.update(_parse(text, BUNDLED_OVERRIDES))
    if extra is not None:
        try:
            text = extra.read_text(encoding="utf-8")
        except OSError as error:
            raise ConfigurationError(f"Cannot read overrides {extra}: {error}") from error
        overrides.update(_parse(text, str(extra)))
    return overrides


def overrides_digest(overrides: Mapping[str, Override]) -> str:
    """A short, order-independent digest, so a cache can tell an edit happened."""
    payload = json.dumps(
        {code: entry.model_dump() for code, entry in sorted(overrides.items())},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]
