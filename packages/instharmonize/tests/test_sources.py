from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from harmonize_core.errors import ConfigurationError, SourceValidationError

from instharmonize.overrides import load_overrides
from instharmonize.sources import read_records


def test_records_group_by_code_and_dataset() -> None:
    with duckdb.connect() as connection:
        connection.execute(
            """
            CREATE TABLE occurrences AS SELECT * FROM (VALUES
                (' MCZ ', 'd1', 'Harvard'),
                ('MCZ', 'd1', 'Harvard'),
                ('MCZ', 'd2', 'Harvard'),
                ('', 'd3', 'Nobody'),
                (NULL, 'd3', 'Nobody')
            ) AS t("institutionCode", "datasetKey", "publisher")
            """
        )
        records = read_records(
            connection, "occurrences", ["institutionCode", "datasetKey", "publisher"]
        )

    counts = {(r.institution_code, r.dataset_key): r.occurrences for r in records}
    assert counts == {("MCZ", "d1"): 2, ("MCZ", "d2"): 1}
    # Columns the source lacks read as None rather than failing.
    assert all(r.institution_id is None for r in records)


def test_source_without_institution_code_is_rejected() -> None:
    with duckdb.connect() as connection, pytest.raises(SourceValidationError):
        read_records(connection, "occurrences", ["datasetKey"])


def test_bundled_overrides_load() -> None:
    overrides = load_overrides()
    assert overrides["TU"].use_publisher


def test_extra_overrides_layer_on_top(tmp_path: Path) -> None:
    extra = tmp_path / "overrides.toml"
    extra.write_text('[institutions.TU]\nname = "Tartu"\n', encoding="utf-8")
    assert load_overrides(extra)["TU"].name == "Tartu"


@pytest.mark.parametrize(
    "entry",
    ['homepage = "https://x.org"', 'name = "X"\nhomepage = "ftp://x.org"', 'nmae = "typo"'],
)
def test_invalid_override_is_a_configuration_error(tmp_path: Path, entry: str) -> None:
    extra = tmp_path / "overrides.toml"
    extra.write_text(f"[institutions.X]\n{entry}\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_overrides(extra, bundled=False)
