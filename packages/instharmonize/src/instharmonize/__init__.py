"""Resolve occurrence institution codes to full names and websites."""

from importlib.metadata import PackageNotFoundError, version

from instharmonize.models import Institution, InstitutionRecord, MatchSource
from instharmonize.resolver import RESOLVER_VERSION, InstitutionResolver

try:
    __version__ = version("instharmonize")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

__all__ = [
    "RESOLVER_VERSION",
    "Institution",
    "InstitutionRecord",
    "InstitutionResolver",
    "MatchSource",
    "__version__",
]
