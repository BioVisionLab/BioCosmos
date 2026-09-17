from pathlib import Path

import duckdb
import pytest

from colharmonize.index import ReferenceIndex
from colharmonize.models import ColumnMappings, MatchingConfig
from colharmonize.pipeline import MatchPipeline
from colharmonize.sources import ColSource, OccurrenceSource


@pytest.mark.benchmark
def test_matching_cardinality_is_independent_of_duplicate_count(
    tmp_path: Path, col_tsv: Path
) -> None:
    index = ReferenceIndex(tmp_path / "cache").ensure(ColSource(col_tsv))
    cardinalities = []
    for copies in (10, 10_000):
        path = tmp_path / f"occurrence-{copies}.duckdb"
        connection = duckdb.connect(str(path))
        connection.execute(
            f"""
            CREATE TABLE occurrence AS
            SELECT CASE WHEN i % 2 = 0 THEN 'Panthera leo' ELSE 'Panthera tigris' END
                       AS species,
                   'Felidae' AS family
            FROM range({copies}) rows(i)
            """
        )
        connection.close()
        source = OccurrenceSource(path, "occurrence")
        mappings = ColumnMappings(scientific_name="species")
        with source.connect() as source_connection:
            columns, _ = source.resolve_columns(
                source.columns(source_connection), mappings, strict=True
            )
        output = duckdb.connect(":memory:")
        try:
            MatchPipeline(output, source, columns, index.path, MatchingConfig()).run()
            cardinalities.append(
                output.execute(
                    "SELECT (SELECT count(*) FROM input_taxa), "
                    "(SELECT count(*) FROM raw_candidates)"
                ).fetchone()
            )
        finally:
            output.close()
    assert cardinalities[0] == cardinalities[1]
    assert cardinalities[0][0] == 2
