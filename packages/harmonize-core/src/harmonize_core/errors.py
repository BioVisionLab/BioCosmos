"""Application exceptions mapped to concise CLI errors."""


class HarmonizeError(Exception):
    """Base class for expected user-facing failures."""


class ConfigurationError(HarmonizeError):
    """Configuration is invalid or incomplete."""


class SourceValidationError(HarmonizeError):
    """An input source is invalid."""


class OutputError(HarmonizeError):
    """An output cannot be created safely."""
