"""Safe DuckDB identifier parsing and quoting."""

from __future__ import annotations

from harmonize_core.errors import SourceValidationError
from harmonize_core.models import TableIdentifier


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parse_table_identifier(value: str) -> TableIdentifier:
    """Parse an optionally quoted table or schema.table identifier."""
    parts: list[str] = []
    current: list[str] = []
    quoted = False
    index = 0
    while index < len(value):
        char = value[index]
        if char == '"':
            if quoted and index + 1 < len(value) and value[index + 1] == '"':
                current.append('"')
                index += 2
                continue
            quoted = not quoted
        elif char == "." and not quoted:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    if quoted:
        raise SourceValidationError(f"Unclosed quote in table identifier: {value}")
    parts.append("".join(current).strip())
    if not 1 <= len(parts) <= 2 or any(not part for part in parts):
        raise SourceValidationError("Table must be TABLE or SCHEMA.TABLE")
    if len(parts) == 1:
        return TableIdentifier(table_name=parts[0])
    return TableIdentifier(schema_name=parts[0], table_name=parts[1])


def qualified_name(identifier: TableIdentifier) -> str:
    return ".".join(
        (quote_identifier(identifier.schema_name), quote_identifier(identifier.table_name))
    )
