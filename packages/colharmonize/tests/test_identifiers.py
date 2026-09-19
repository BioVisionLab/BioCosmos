import pytest

from colharmonize.errors import SourceValidationError
from colharmonize.identifiers import parse_table_identifier, qualified_name


def test_quoted_table_identifier() -> None:
    parsed = parse_table_identifier('"tax schema"."tax.table"')
    assert parsed.schema_name == "tax schema"
    assert parsed.table_name == "tax.table"
    assert qualified_name(parsed) == '"tax schema"."tax.table"'


def test_invalid_identifier_is_rejected() -> None:
    with pytest.raises(SourceValidationError):
        parse_table_identifier("catalog.schema.table")
