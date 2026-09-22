from __future__ import annotations

from pathlib import Path

import pytest
from harmonize_core.errors import ConfigurationError

from plannerbench.cases import check_cases_against_spec, load_cases


def test_packaged_cases_load_and_fit_the_spec(spec) -> None:
    cases = load_cases()
    assert len(cases) >= 10
    check_cases_against_spec(cases, spec)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "cases.toml"
    path.write_text(
        '[[cases]]\nid = "a"\nquery = "x"\naccept = [{}]\n'
        '[[cases]]\nid = "a"\nquery = "y"\naccept = [{}]\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="Duplicate case id"):
        load_cases(path)


def test_unknown_tools_are_rejected(tmp_path: Path, spec) -> None:
    path = tmp_path / "cases.toml"
    path.write_text(
        '[[cases]]\nid = "a"\nquery = "x"\naccept = [{ search_by_weather = {} }]\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="search_by_weather"):
        check_cases_against_spec(load_cases(path), spec)
