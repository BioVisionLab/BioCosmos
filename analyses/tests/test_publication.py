"""Verify scientific denominators and complete notebook execution."""

import hashlib
from dataclasses import replace

import duckdb
import matplotlib.pyplot as plt
import nbformat
import pytest
from analyses.publication import (
    AnalysisError,
    bar_plot,
    benchmark_data,
    connect,
    dataset_summaries,
    geography_summaries,
    load_settings,
    project_root,
    taxonomy_summaries,
)
from nbclient import NotebookClient


def as_counts(frame):
    return dict(zip(frame["category"], frame["count"], strict=True))


def test_dataset_counts_harmonized_taxonomy_and_duplicate_gbif(settings):
    summaries = dataset_summaries(settings)
    assert as_counts(summaries["family"]) == {
        "Nymphalidae": 3,
        "Pieridae": 2,
        "Unresolved": 3,
    }
    assert as_counts(summaries["species"]) == {
        "Danaus plexippus": 3,
        "Pieris rapae": 1,
        "Unresolved": 4,
    }
    assert as_counts(summaries["institutions"]) == {
        "MUSEUM": 2,
        "B": 2,
        "Conflicting attribution": 1,
        "Unattributed": 3,
    }
    assert as_counts(summaries["views"]) == {
        "dorsal": 3,
        "ventral": 2,
        "lateral": 1,
        "Unknown": 2,
    }
    for frame in summaries.values():
        assert frame["count"].sum() == 8
        assert frame["percentage"].sum() == pytest.approx(100)
        assert set(frame["denominator"]) == {8}


def test_geography_availability_is_not_validation(settings):
    summaries = geography_summaries(settings)
    assert as_counts(summaries["coordinate_availability"]) == {
        "With coordinate pair": 5,
        "Missing or unparseable pair": 3,
    }
    assert as_counts(summaries["locality_availability"]) == {
        "Detailed locality available": 3,
        "No detailed locality": 5,
    }
    assert as_counts(summaries["coordinate_validation"]) == {
        "VALID": 2,
        "MISSING_COORDINATE": 3,
        "ZERO_COORDINATE": 1,
        "COORDINATE_OUT_OF_RANGE": 1,
        "NOT_EVALUATED": 1,
    }


def test_taxonomy_uses_referenced_taxa_and_full_denominators(settings):
    summaries = taxonomy_summaries(settings)
    assert as_counts(summaries["images_status"]) == {
        "MATCHED": 5,
        "AMBIGUOUS": 1,
        "UNMATCHED": 1,
        "UNCLASSIFIED": 1,
    }
    assert as_counts(summaries["taxa_status"]) == {"MATCHED": 4, "AMBIGUOUS": 1, "UNMATCHED": 1}
    for name, frame in summaries.items():
        assert frame["percentage"].sum() == pytest.approx(100)
        assert frame["count"].sum() == (8 if name.startswith("images") else 6)


@pytest.mark.parametrize(
    "table,key",
    [
        ("image_meta", "img_id"),
        ("image_meta_taxonomy", "img_id"),
        ("image_meta_locality", "img_id"),
        ("image_meta_coordinates", "source_id"),
    ],
)
def test_fanout_rejected(settings, table, key):
    with duckdb.connect(str(settings.database)) as connection:
        connection.execute(f"INSERT INTO {table} SELECT * FROM {table} LIMIT 1")
    function = (
        geography_summaries
        if table
        in {
            "image_meta_locality",
            "image_meta_coordinates",
        }
        else dataset_summaries
    )
    with pytest.raises(AnalysisError, match="one nonblank row key"):
        function(settings)


def test_code_collisions_are_not_merged(settings):
    with duckdb.connect(str(settings.database)) as connection:
        connection.execute("""
            INSERT INTO gbif_meta VALUES ('u6', 'museum-c', 'MUSEUM');
            DELETE FROM gbif_meta WHERE occurrenceID = 'u1' AND institutionID IS NULL;
            INSERT INTO gbif_meta VALUES ('u4', NULL, 'MUSEUM');
        """)
    result = as_counts(dataset_summaries(settings)["institutions"])
    assert result["MUSEUM [museum-a]"] == 2
    assert result["MUSEUM [museum-c]"] == 1
    assert result["Conflicting attribution"] == 2


def test_missing_prepared_table_is_actionable(settings):
    with duckdb.connect(str(settings.database)) as connection:
        connection.execute("DROP TABLE image_meta_coordinates")
    with pytest.raises(AnalysisError, match="geoharmonize integrate"):
        geography_summaries(settings)


def test_database_is_read_only(settings):
    before = hashlib.sha256(settings.database.read_bytes()).hexdigest()
    dataset_summaries(settings)
    geography_summaries(settings)
    taxonomy_summaries(settings)
    assert hashlib.sha256(settings.database.read_bytes()).hexdigest() == before
    with connect(settings) as connection, pytest.raises(duckdb.Error):
        connection.execute("CREATE TABLE forbidden (id INTEGER)")


def test_ranking_ties_and_denominator(settings):
    frame = dataset_summaries(settings)["institutions"]
    fig, ax = plt.subplots()
    bar_plot(ax, frame, "Institutions", top=2, exclude=("Unattributed", "Conflicting attribution"))
    assert [label.get_text() for label in ax.get_yticklabels()] == ["B", "MUSEUM"]
    assert [bar.get_width() for bar in ax.patches] == [25, 25]
    plt.close(fig)


def test_config_is_independent_of_notebook_working_directory(monkeypatch):
    root = project_root()
    monkeypatch.setenv("DUCK_DIR", "relative-duck")
    monkeypatch.delenv("BIOCOSMOS_ANALYSES_OUTPUT", raising=False)
    monkeypatch.chdir(root / "analyses/notebooks")
    settings = load_settings()
    assert settings.database == root / "backend/relative-duck/biocosmos.duckdb"
    assert settings.output == root / "analyses/results"
    monkeypatch.setenv("BIOCOSMOS_ANALYSES_OUTPUT", "/tmp/outside-analyses")
    with pytest.raises(AnalysisError, match="inside analyses"):
        load_settings()


def test_missing_database_does_not_create_file(settings, tmp_path):
    path = tmp_path / "missing.duckdb"
    with pytest.raises(AnalysisError, match="Database not found"):
        with connect(replace(settings, database=path)):
            pass
    assert not path.exists()


def test_benchmark_preserves_existing_exclusion():
    frame = benchmark_data()
    assert "Flat (brute-force)" not in set(frame["index"])
    assert "No Index (baseline)" in set(frame["index"])


@pytest.mark.parametrize(
    "name", ["data_summary", "georeference", "taxonomy_harmonization", "index_perf"]
)
def test_notebook_executes_with_fixture_data(settings, monkeypatch, name):
    root = project_root()
    output = root / "analyses/results/fixture-validation"
    output.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DUCK_DIR", str(settings.database.parent))
    monkeypatch.setenv("BIOCOSMOS_ANALYSES_OUTPUT", str(output))
    monkeypatch.setenv("MPLBACKEND", "Agg")
    notebook_path = root / "analyses/notebooks" / f"{name}.ipynb"
    notebook = nbformat.read(notebook_path, as_version=4)
    nbformat.validate(notebook)
    # The saved source stays clean. Executed copies and fixture figures are
    # visibly isolated from real publication outputs.
    before = notebook_path.read_bytes()
    NotebookClient(
        notebook,
        timeout=120,
        kernel_name="python3",
        resources={
            "metadata": {"path": str(root / "analyses/notebooks")},
        },
    ).execute()
    nbformat.write(notebook, output / f"{name}.ipynb")
    assert notebook_path.read_bytes() == before
    assert all(not cell.get("outputs") for cell in nbformat.read(notebook_path, as_version=4).cells)
