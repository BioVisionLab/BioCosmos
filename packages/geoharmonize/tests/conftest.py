from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import duckdb
import pytest
from shapely import to_wkb
from shapely.geometry import Polygon


@pytest.fixture
def coordinate_db(tmp_path: Path) -> Path:
    path = tmp_path / "coordinates.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        CREATE TABLE occurrence(
            occurrenceID VARCHAR,
            decimalLatitude VARCHAR,
            decimalLongitude VARCHAR,
            country VARCHAR,
            stateProvince VARCHAR
        )
        """
    )
    connection.executemany(
        "INSERT INTO occurrence VALUES (?, ?, ?, ?, ?)",
        [
            ("valid-name", "5", "5", "United States", "Florida State"),
            ("valid-code", "5", "5", "US", "Florida"),
            ("valid-no-locality", "5", "5", None, None),
            ("country-mismatch", "5", "5", "Canada", "Florida"),
            ("adm1-mismatch", "5", "5", "USA", "Georgia"),
            ("missing", None, "5", "USA", "Florida"),
            ("unparseable", "north", "5", "USA", "Florida"),
            ("latitude-range", "95", "5", "USA", "Florida"),
            ("longitude-range", "5", "190", "USA", "Florida"),
            ("zero", "0", "0", "USA", "Florida"),
            ("no-reference", "50", "50", "USA", "Florida"),
            ("ambiguous", "5", "8.5", "USA", "Florida"),
        ],
    )
    connection.close()
    return path


def _gpkg_geometry(polygon: Polygon) -> bytes:
    return b"GP\x00\x01" + struct.pack("<i", 4326) + to_wkb(polygon)


@pytest.fixture
def gadm_gpkg(tmp_path: Path) -> Path:
    path = tmp_path / "gadm.gpkg"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE gpkg_spatial_ref_sys(
            srs_name TEXT NOT NULL,
            srs_id INTEGER NOT NULL PRIMARY KEY,
            organization TEXT NOT NULL,
            organization_coordsys_id INTEGER NOT NULL,
            definition TEXT NOT NULL,
            description TEXT
        );
        INSERT INTO gpkg_spatial_ref_sys VALUES
            ('WGS 84 geodetic', 4326, 'EPSG', 4326, 'WGS84', NULL);

        CREATE TABLE gpkg_geometry_columns(
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            geometry_type_name TEXT NOT NULL,
            srs_id INTEGER NOT NULL,
            z TINYINT NOT NULL,
            m TINYINT NOT NULL,
            PRIMARY KEY(table_name, column_name)
        );

        CREATE TABLE ADM_ADM_1(
            fid INTEGER PRIMARY KEY,
            GID_0 TEXT NOT NULL,
            COUNTRY TEXT NOT NULL,
            GID_1 TEXT NOT NULL,
            NAME_1 TEXT NOT NULL,
            geom BLOB NOT NULL
        );
        INSERT INTO gpkg_geometry_columns VALUES
            ('ADM_ADM_1', 'geom', 'POLYGON', 4326, 0, 0);
        CREATE VIRTUAL TABLE rtree_ADM_ADM_1_geom USING rtree(
            id, minx, maxx, miny, maxy
        );
        """
    )
    features = [
        (
            1,
            "USA",
            "United States",
            "USA.10_1",
            "Florida",
            Polygon([(1, 1), (9, 1), (9, 9), (1, 9), (1, 1)]),
        ),
        (
            2,
            "CAN",
            "Canada",
            "CAN.9_1",
            "Ontario",
            Polygon([(11, 1), (19, 1), (19, 9), (11, 9), (11, 1)]),
        ),
        (
            3,
            "CAN",
            "Canada",
            "CAN.99_1",
            "Overlap",
            Polygon([(8, 4), (12, 4), (12, 6), (8, 6), (8, 4)]),
        ),
    ]
    for feature_id, gid0, country, gid1, adm1, polygon in features:
        connection.execute(
            "INSERT INTO ADM_ADM_1 VALUES (?, ?, ?, ?, ?, ?)",
            [feature_id, gid0, country, gid1, adm1, _gpkg_geometry(polygon)],
        )
        min_x, min_y, max_x, max_y = polygon.bounds
        connection.execute(
            "INSERT INTO rtree_ADM_ADM_1_geom VALUES (?, ?, ?, ?, ?)",
            [feature_id, min_x, max_x, min_y, max_y],
        )
    connection.commit()
    connection.close()
    return path
