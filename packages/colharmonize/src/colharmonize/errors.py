"""Application exceptions mapped to concise CLI errors."""


class ColHarmonizeError(Exception):
    """Base class for expected user-facing failures."""


class ConfigurationError(ColHarmonizeError):
    """Configuration is invalid or incomplete."""


class SourceValidationError(ColHarmonizeError):
    """An occurrence or Catalogue of Life source is invalid."""


class OutputError(ColHarmonizeError):
    """An output cannot be created safely."""
