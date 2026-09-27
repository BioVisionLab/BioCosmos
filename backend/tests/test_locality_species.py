"""The agent location filter: GADM-first country and ADM1 matching."""

from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest

from app.query.locality_species import LocalitySpecies
from app.services.agent import FILTER_SPECIES_LIMIT, AgentSearchService

LOCALITY_DDL = """
    CREATE TABLE image_meta_locality (
        img_id VARCHAR, country_code VARCHAR, state_province VARCHAR
    )
"""

COORDINATES_DDL = """
    CREATE TABLE image_meta_coordinates (
        source_id VARCHAR, reference_gid_0 VARCHAR, reference_adm1 VARCHAR
    )
"""

# img_id, species, recorded country, recorded ADM1, GADM GID_0, GADM ADM1
ROWS = [
    ("i1", "Morpho helenor", "BR", "Sao Paulo State", None, None),
    ("i2", "Heliconius erato", "BR", "SP", "BRA", "São Paulo"),
    ("i3", "Danaus plexippus", "BR", "Minas Gerais", "BRA", "Minas Gerais"),
    # Recorded as Brazil, but the coordinate falls in Peru.
    ("i4", "Morpho menelaus", "BR", "Acre", "PER", "Madre de Dios"),
    # No GADM reference: the recorded country and ADM1 stand.
    ("i5", "Troides amphrysus", "my", "Sabah", None, None),
    ("i6", "Papilio demoleus", None, None, "MYS", "Sabah"),
    ("i7", None, "BR", "Bahia", None, None),
]


def _seed(client, *, coordinates: bool = True):
    client.execute("CREATE TABLE image_meta (img_id VARCHAR, species VARCHAR)")
    client.execute(LOCALITY_DDL)
    if coordinates:
        client.execute(COORDINATES_DDL)
    for img_id, species, country, adm1, gid_0, ref_adm1 in ROWS:
        client.execute_prepared(
            "INSERT INTO image_meta VALUES (?, ?)", [img_id, species]
        )
        client.execute_prepared(
            "INSERT INTO image_meta_locality VALUES (?, ?, ?)",
            [img_id, country, adm1],
        )
        if coordinates:
            client.execute_prepared(
                "INSERT INTO image_meta_coordinates VALUES (?, ?, ?)",
                [img_id, gid_0, ref_adm1],
            )
    return client


@pytest.fixture
def seeded(memory_duckdb):
    return _seed(memory_duckdb)


def test_gadm_reference_overrides_recorded_country(seeded):
    service = LocalitySpecies(seeded)

    assert service.species("BR") == [
        "Danaus plexippus",
        "Heliconius erato",
        "Morpho helenor",
    ]
    assert service.species("pe") == ["Morpho menelaus"]


def test_falls_back_to_recorded_locality_without_reference(seeded):
    assert LocalitySpecies(seeded).species("MY") == [
        "Papilio demoleus",
        "Troides amphrysus",
    ]


def test_adm1_matches_gadm_and_recorded_names_loosely(seeded):
    service = LocalitySpecies(seeded)

    # "São Paulo" from GADM and "Sao Paulo State" as recorded both match.
    assert service.species("BR", "sao paulo") == ["Heliconius erato", "Morpho helenor"]
    assert service.species("BR", "São Paulo Province") == [
        "Heliconius erato",
        "Morpho helenor",
    ]
    assert service.species("MY", "Sabah") == ["Papilio demoleus", "Troides amphrysus"]


def test_adm1_does_not_cross_countries(seeded):
    service = LocalitySpecies(seeded)

    # i4 was recorded in Acre, but GADM files it under Peru.
    assert service.species("BR", "Acre") == []
    assert service.species("PE", "Madre de Dios") == ["Morpho menelaus"]


def test_unknown_adm1_is_an_empty_hard_filter(seeded):
    assert LocalitySpecies(seeded).species("BR", "Queensland") == []


def test_works_without_coordinate_table(memory_duckdb):
    service = LocalitySpecies(_seed(memory_duckdb, coordinates=False))

    assert service.available()
    assert service.species("BR") == [
        "Danaus plexippus",
        "Heliconius erato",
        "Morpho helenor",
        "Morpho menelaus",
    ]
    assert service.species("BR", "Acre") == ["Morpho menelaus"]
    assert service.species("MY") == ["Troides amphrysus"]


def test_unavailable_without_locality_table(memory_duckdb):
    memory_duckdb.execute("CREATE TABLE image_meta (img_id VARCHAR, species VARCHAR)")

    assert not LocalitySpecies(memory_duckdb).available()


def test_rejects_non_iso_code(seeded):
    with pytest.raises(ValueError):
        LocalitySpecies(seeded).species("Brazil")


def test_values_are_bound_not_interpolated():
    client = MagicMock()
    client.missing_tables.return_value = []
    client.execute_prepared_to_pl.side_effect = [
        pl.DataFrame({"adm1": ["O'Higgins"]}),
        pl.DataFrame({"species": ["Species a"]}),
    ]

    result = LocalitySpecies(client).species("cl", "O'Higgins", limit=25)

    sql, params = client.execute_prepared_to_pl.call_args.args
    assert "O'Higgins" not in sql
    assert "CL" not in sql
    assert params == ["CHL", "CL", "O'Higgins", 25]
    assert result == ["Species a"]


class _LocationHarness(NamedTuple):
    service: AgentSearchService
    locality_species: MagicMock
    gbif_service: MagicMock
    species_to_filter_rows: AsyncMock


def _location_service(available: bool) -> _LocationHarness:
    locality_species = MagicMock()
    locality_species.available.return_value = available
    locality_species.species.return_value = ["Species a"]
    gbif_service = MagicMock()
    gbif_service.search_by_country_code.return_value = ["Species b"]
    species_to_filter_rows = AsyncMock(return_value=[])
    service = AgentSearchService.__new__(AgentSearchService)
    service.locality_species = locality_species
    service.gbif_service = gbif_service
    service._species_to_filter_rows = species_to_filter_rows
    return _LocationHarness(
        service, locality_species, gbif_service, species_to_filter_rows
    )


@pytest.mark.asyncio
async def test_agent_location_uses_locality_filter():
    harness = _location_service(available=True)

    await harness.service._search_by_location("MY", "Sabah")

    harness.locality_species.species.assert_called_once_with(
        "MY", "Sabah", FILTER_SPECIES_LIMIT
    )
    harness.gbif_service.search_by_country_code.assert_not_called()
    harness.species_to_filter_rows.assert_awaited_once_with(
        ["Species a"], tool_name="search_by_location"
    )


@pytest.mark.asyncio
async def test_agent_location_falls_back_to_recorded_country():
    harness = _location_service(available=False)

    await harness.service._search_by_location("MY", "Sabah")

    harness.gbif_service.search_by_country_code.assert_called_once_with(
        "MY", FILTER_SPECIES_LIMIT
    )
    harness.species_to_filter_rows.assert_awaited_once_with(
        ["Species b"], tool_name="search_by_location"
    )
