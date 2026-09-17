from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import duckdb

from colharmonize.index import ReferenceIndex
from colharmonize.sources import ColSource


def test_index_resolves_synonym_and_reuses_cache(col_tsv: Path, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    manager = ReferenceIndex(cache)
    first = manager.ensure(ColSource(col_tsv))
    second = manager.ensure(ColSource(col_tsv))
    assert not first.reused
    assert second.reused
    connection = duckdb.connect(str(first.path), read_only=True)
    try:
        accepted_id = connection.execute(
            "SELECT accepted_id FROM usage_lookup WHERE usage_id = 'S1'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert accepted_id == "A1"


def test_coldp_zip_is_supported(col_tsv: Path, tmp_path: Path) -> None:
    archive = tmp_path / "col.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as output:
        output.write(col_tsv, "dataset/name-usage.tsv")
    info = ReferenceIndex(tmp_path / "cache").ensure(ColSource(archive))
    assert info.accepted_count == 6
