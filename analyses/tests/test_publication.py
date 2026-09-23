"""Verify scientific denominators and complete notebook execution."""

import hashlib
from dataclasses import replace

import duckdb
import matplotlib.pyplot as plt
import nbformat
import pandas as pd
import pytest
import seaborn as sns
from analyses.helpers.publication import (
    DEFAULT_PALETTE,
    AnalysisError,
    align_panel_titles,
    bar_plot,
    benchmark_data,
    category_plot,
    connect,
    dataset_summaries,
    geography_summaries,
    load_settings,
    project_root,
    taxonomy_summaries,
    top_share,
)
from matplotlib.colors import to_hex
from matplotlib.text import Text
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
    # Recorded aggregator keys print in their published form; a record carried by
    # two aggregators keeps its combined key instead of counting under each one.
    assert as_counts(summaries["sources"]) == {
        "GBIF": 4,
        "GBIF / SCAN": 1,
        "SCAN": 1,
        "Ecdysis": 1,
        "Unknown": 1,
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
    assert [label.get_text() for label in ax.get_yticklabels()] == ["B", "Museum"]
    assert [bar.get_width() for bar in ax.patches] == [25, 25]
    plt.close(fig)


def test_bars_use_one_palette_color(settings):
    frame = dataset_summaries(settings)["family"]
    fig, ax = plt.subplots()
    category_plot(ax, frame, "Family")
    expected = sns.color_palette(DEFAULT_PALETTE)[0]
    assert {bar.get_facecolor()[:3] for bar in ax.patches} == {expected}
    plt.close(fig)


def test_two_class_summaries_become_pies(settings):
    summaries = geography_summaries(settings)
    fig, axes = plt.subplots(1, 3)
    category_plot(axes[0], summaries["coordinate_availability"], "Coordinates")
    category_plot(axes[1], summaries["coordinate_validation"], "Validation")
    category_plot(axes[2], summaries["coordinate_availability"], "Coordinates", kind="bar")
    wedges, bars = [ax.patches for ax in axes[:2]], axes[2].patches
    assert [len(patches) for patches in wedges] == [2, 5]
    assert {type(patch).__name__ for patch in wedges[0]} == {"Wedge"}
    # More than two classes, and an explicit override, stay bars.
    assert {type(patch).__name__ for patch in wedges[1] + list(bars)} == {"Rectangle"}
    # Pie shares live in a legend, so adjacent small wedges cannot overlap labels.
    assert not any(text.get_text() for text in axes[0].texts)
    assert [text.get_text() for text in axes[0].get_legend().get_texts()] == [
        "With coordinate pair: 5 (62.5%)",
        "Missing or unparseable pair: 3 (37.5%)",
    ]
    assert [label.get_text() for label in axes[1].get_yticklabels()] == [
        "Missing coordinate",
        "Valid",
        "Coordinate out of range",
        "Not evaluated",
        "Zero coordinate",
    ]
    plt.close(fig)


def test_italic_pie_styles_its_legend(settings):
    frame = taxonomy_summaries(settings)["images_status"]
    fig, ax = plt.subplots()
    category_plot(ax, frame, "Status", kind="pie", italic=True)
    assert {text.get_fontstyle() for text in ax.get_legend().get_texts()} == {"italic"}
    plt.close(fig)


def test_top_share_pie_keeps_the_whole_and_recorded_case(settings):
    frame = dataset_summaries(settings)["institutions"]
    shares = top_share(
        frame,
        1,
        exclude=("Unattributed", "Conflicting attribution"),
        other="Other institutions",
        excluded="Unattributed or conflicting",
    )
    # Ties rank alphabetically: B before MUSEUM; unattributed and conflicting pool.
    assert as_counts(shares) == {
        "B": 2,
        "Other institutions": 2,
        "Unattributed or conflicting": 4,
    }
    assert shares["count"].sum() == shares["denominator"].iloc[0] == 8
    assert shares["percentage"].sum() == pytest.approx(100)
    fig, ax = plt.subplots()
    category_plot(ax, shares, "Institutions", kind="pie", keep_case=True)
    assert [text.get_text() for text in ax.get_legend().get_texts()] == [
        "B: 2 (25.0%)",
        "Other institutions: 2 (25.0%)",
        "Unattributed or conflicting: 4 (50.0%)",
    ]
    # Residual groups follow the ranked share in gray, whatever their size.
    colors = [to_hex(wedge.get_facecolor()) for wedge in ax.patches]
    assert colors == [to_hex(sns.color_palette(DEFAULT_PALETTE)[0]), "#999999", "#cccccc"]
    plt.close(fig)


def left_title(ax):
    """The artist holding a loc="left" title, which is not ``ax.title``."""
    text = ax.get_title(loc="left")
    return next(
        child for child in ax.get_children() if isinstance(child, Text) and child.get_text() == text
    )


def test_panel_titles_share_one_heading_line(settings):
    summaries = dataset_summaries(settings)
    fig, axes = plt.subplots(1, 2, figsize=(8, 3), layout="constrained")
    category_plot(axes[0], summaries["views"], "A) Views")
    category_plot(axes[1], summaries["species"], "B) Species", top=2, exclude=("Unresolved",))
    # One panel carries a subtitle line and the other does not, as in the notebook,
    # where the shared "N =" line moves to the figure title.
    axes[0].set_title("A) Views", loc="left")
    axes[1].set_title("B) Species\nunresolved excluded: 4", loc="left")
    fig.canvas.draw()
    fig.set_layout_engine(None)
    align_panel_titles(axes)
    fig.canvas.draw()
    # The shorter title is padded, so both headings sit on the same line.
    assert [len(ax.get_title(loc="left").split("\n")) for ax in axes] == [2, 2]
    tops = [left_title(ax).get_window_extent().y1 for ax in axes]
    # Within a pixel: the tops differ only by the tallest glyph on each line.
    assert tops[0] == pytest.approx(tops[1], abs=2)
    plt.close(fig)


def test_pie_refuses_a_ranked_subset(settings):
    frame = dataset_summaries(settings)["institutions"]
    fig, ax = plt.subplots()
    with pytest.raises(ValueError, match="whole population"):
        category_plot(ax, frame, "Institutions", kind="pie", top=2)
    plt.close(fig)


def test_every_pie_shares_one_color_sequence(settings):
    availability = geography_summaries(settings)["coordinate_availability"]
    status = taxonomy_summaries(settings)["images_status"]
    fig, axes = plt.subplots(1, 3)
    category_plot(axes[0], availability, "Coordinates")
    category_plot(axes[1], status, "Status", kind="pie")
    category_plot(axes[2], status, "Status", kind="pie", palette="muted")
    dark2, muted = sns.color_palette(DEFAULT_PALETTE), sns.color_palette("muted")
    colors = [[wedge.get_facecolor()[:3] for wedge in ax.patches] for ax in axes]
    assert colors[0] == dark2[:2]
    assert colors[1] == dark2[:4]
    assert colors[2] == muted[:4]
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


@pytest.mark.parametrize("name", ["data_summary", "harmonization", "index_perf"])
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

    if name == "data_summary":
        richness = pd.read_csv(
            output / "dataset_overview_country_species.csv", keep_default_na=False
        )
        # Only VALID coordinates map, by their GADM country; the fixture's raw
        # locality countries (including CA for i3) are ignored.
        assert dict(zip(richness.country_code, richness.species_count)) == {"US": 1}
        assert dict(zip(richness.country_code, richness.image_count)) == {"US": 2}
        assert set(richness.loc[richness.mapped, "country_code"]) == {"US"}
