"""Georeferenced specimens for the species distribution map."""

import pytest

from app.query.species_coordinates import SpeciesCoordinates

IMAGE_DDL = """
    CREATE TABLE image_meta (
        img_id VARCHAR, species VARCHAR, uuid VARCHAR, class_dv VARCHAR,
        lat DOUBLE, lon DOUBLE, source_db VARCHAR, sex VARCHAR
    )
"""

COORDINATES_DDL = """
    CREATE TABLE image_meta_coordinates (
        source_id VARCHAR, validation_status VARCHAR,
        recorded_country VARCHAR, recorded_adm1 VARCHAR,
        reference_country VARCHAR, reference_adm1 VARCHAR
    )
"""

# img_id, species, uuid, side, lat, lon, source, sex
IMAGES = [
    # One specimen, both sides: one point, dorsal kept.
    ("a-v", "danaus_plexippus", "occ-1", "ventral", 10.0, 20.0, "MCZ", "male"),
    ("a-d", "danaus_plexippus", "occ-1", "dorsal", 10.0, 20.0, "MCZ", "male"),
    # No occurrence ID: the image is its own specimen.
    ("b", "Danaus plexippus", "", "dorsal", -5.5, 100.25, "FLMNH", None),
    # Unusable coordinates are dropped.
    ("c", "danaus_plexippus", "occ-3", "dorsal", None, 20.0, "MCZ", None),
    ("d", "danaus_plexippus", "occ-4", "dorsal", 95.0, 20.0, "MCZ", None),
    ("e", "morpho_helenor", "occ-5", "dorsal", 1.0, 1.0, "MCZ", None),
]

VALIDATION = [
    ("a-d", "VALID", "Brazil", "Sao Paulo", "Brazil", "São Paulo"),
    ("a-v", "COUNTRY_MISMATCH", "Brazil", None, "Peru", None),
    ("b", "ADM1_MISMATCH", "Indonesia", "Bali", "Indonesia", "Aceh"),
]


PROVENANCE = [
    ("a-d", "MCZ", "165381"),
    ("a-v", "MCZ", "165381"),
    ("b", "ZZZ", "FL-9"),
]

INSTITUTIONS = [("MCZ", "Museum of Comparative Zoology")]


def _seed(client, *, coordinates: bool = True, provenance: bool = True):
    client.execute(IMAGE_DDL)
    for row in IMAGES:
        client.execute_prepared(
            "INSERT INTO image_meta VALUES (?, ?, ?, ?, ?, ?, ?, ?)", list(row)
        )
    if coordinates:
        client.execute(COORDINATES_DDL)
        for row in VALIDATION:
            client.execute_prepared(
                "INSERT INTO image_meta_coordinates VALUES (?, ?, ?, ?, ?, ?)",
                list(row),
            )
    if provenance:
        client.execute(
            "CREATE TABLE image_meta_provenance ("
            "img_id VARCHAR, institution_code VARCHAR, catalog_number VARCHAR)"
        )
        for row in PROVENANCE:
            client.execute_prepared(
                "INSERT INTO image_meta_provenance VALUES (?, ?, ?)", list(row)
            )
        client.execute(
            "CREATE TABLE institution_directory (code VARCHAR, name VARCHAR)"
        )
        for row in INSTITUTIONS:
            client.execute_prepared(
                "INSERT INTO institution_directory VALUES (?, ?)", list(row)
            )
    return client


@pytest.mark.parametrize(
    "name", ["danaus_plexippus", "Danaus plexippus", "  DANAUS   plexippus "]
)
def test_one_point_per_specimen(memory_duckdb, name):
    payload = SpeciesCoordinates(_seed(memory_duckdb)).get(name)

    assert payload["total"] == 2
    assert payload["truncated"] is False
    points = {point["imgId"]: point for point in payload["points"]}
    assert set(points) == {"a-d", "b"}
    assert points["a-d"]["imageCount"] == 2
    assert points["a-d"]["sides"] == ["dorsal", "ventral"]
    assert points["b"]["sides"] == ["dorsal"]
    assert points["a-d"]["validationStatus"] == "VALID"
    assert points["a-d"]["referenceAdm1"] == "São Paulo"
    # The locality as recorded, for the card to set beside the reference.
    assert points["b"]["recordedAdm1"] == "Bali"
    assert points["b"]["referenceAdm1"] == "Aceh"
    assert points["a-d"]["catalogNumber"] == "165381"
    assert points["a-d"]["institutionName"] == "Museum of Comparative Zoology"
    # A code the directory cannot name still identifies the holder.
    assert points["b"]["institutionCode"] == "ZZZ"
    assert points["b"]["institutionName"] is None
    assert points["b"]["imageCount"] == 1
    assert points["b"]["sex"] is None
    assert (points["b"]["lat"], points["b"]["lon"]) == (-5.5, 100.25)


def test_without_optional_tables_keeps_shape(memory_duckdb):
    client = _seed(memory_duckdb, coordinates=False, provenance=False)
    payload = SpeciesCoordinates(client).get("danaus_plexippus")

    assert len(payload["points"]) == 2
    for point in payload["points"]:
        assert point["validationStatus"] is None
        assert point["referenceCountry"] is None
        assert point["catalogNumber"] is None
        assert point["institutionName"] is None


def test_recorded_locality_prefers_the_locality_table(memory_duckdb):
    # The validation table keeps the source's own country value, often a bare
    # ISO code; the locality table has the name the metadata panel shows.
    client = _seed(memory_duckdb)
    client.execute(
        "CREATE TABLE image_meta_locality ("
        "img_id VARCHAR, country VARCHAR, state_province VARCHAR)"
    )
    client.execute_prepared(
        "INSERT INTO image_meta_locality VALUES (?, ?, ?)",
        ["b", "Indonesia (recorded)", None],
    )
    payload = SpeciesCoordinates(client).get("danaus_plexippus")
    points = {point["imgId"]: point for point in payload["points"]}

    assert points["b"]["recordedCountry"] == "Indonesia (recorded)"
    # A rank the locality table lacks falls back to the validation table's.
    assert points["b"]["recordedAdm1"] == "Bali"
    assert points["a-d"]["recordedCountry"] == "Brazil"


def test_truncation_is_reported(memory_duckdb):
    payload = SpeciesCoordinates(_seed(memory_duckdb), limit=1).get("danaus_plexippus")

    assert payload["total"] == 2
    assert payload["truncated"] is True
    assert len(payload["points"]) == 1


@pytest.mark.parametrize("name", ["unknown_species", "", "   "])
def test_no_points_is_none(memory_duckdb, name):
    assert SpeciesCoordinates(_seed(memory_duckdb)).get(name) is None


UMAP_DDL = """
    CREATE TABLE umap_embeddings (
        img_id VARCHAR, species VARCHAR, "UMAP1" DOUBLE, "UMAP2" DOUBLE,
        cluster_label INTEGER, "index" INTEGER
    )
"""


def test_umap_points_carry_the_specimen_record(memory_duckdb):
    from app.services.umap import SpeciesImageUmap

    client = _seed(memory_duckdb)
    client.execute(UMAP_DDL)
    client.execute_prepared(
        "INSERT INTO umap_embeddings VALUES (?, ?, ?, ?, ?, ?)",
        ["a-v", "danaus_plexippus", 1.0, 2.0, 3, 0],
    )

    (point,) = SpeciesImageUmap(client).get_embeddings("danaus_plexippus")[
        "umapEmbeddings"
    ]

    assert point["clusterLabel"] == 3
    assert point["classDv"] == "ventral"
    assert point["catalogNumber"] == "165381"
    assert point["institutionName"] == "Museum of Comparative Zoology"
    assert point["validationStatus"] == "COUNTRY_MISMATCH"
    assert point["recordedCountry"] == "Brazil"
    assert point["referenceCountry"] == "Peru"


def test_umap_points_without_optional_tables(memory_duckdb):
    from app.services.umap import SpeciesImageUmap

    client = _seed(memory_duckdb, coordinates=False, provenance=False)
    client.execute(UMAP_DDL)
    client.execute_prepared(
        "INSERT INTO umap_embeddings VALUES (?, ?, ?, ?, ?, ?)",
        ["a-d", "danaus_plexippus", 1.0, 2.0, 0, 0],
    )

    (point,) = SpeciesImageUmap(client).get_embeddings("danaus_plexippus")[
        "umapEmbeddings"
    ]

    assert point["catalogNumber"] is None
    assert point["validationStatus"] is None
