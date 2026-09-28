"""Dorso-ventral morphospaces, disparity and integration from image embeddings."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("morphospace")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

__all__ = ["__version__"]
