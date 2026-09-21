"""Shared building blocks for the harmonize command-line tools."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("harmonize-core")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

__all__ = ["__version__"]
