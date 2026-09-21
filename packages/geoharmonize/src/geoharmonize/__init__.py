"""Coordinate validation against GADM administrative geography."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("geoharmonize")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

__all__ = ["__version__"]
