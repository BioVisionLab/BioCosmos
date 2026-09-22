"""Small, intentionally imperfect collection for publication regression checks."""

from dataclasses import replace

import duckdb
import pytest
from analyses.helpers.publication import load_settings


@pytest.fixture
def settings(tmp_path):
    database = tmp_path / "biocosmos.duckdb"
    with duckdb.connect(str(database)) as connection:
        connection.execute("""
            CREATE TABLE image_meta (
                img_id VARCHAR, uuid VARCHAR, class_dv VARCHAR, lat VARCHAR, lon VARCHAR,
                source_db VARCHAR
            );
            INSERT INTO image_meta VALUES
                ('i1', 'u1', 'dorsal', '10', '20', 'gbif'),
                ('i2', 'u1', 'ventral', '10', '20', 'gbif'),
                ('i3', 'u2', 'dorsal', '10', NULL, 'gbif/scanbugs'),
                ('i4', 'u3', NULL, 'NaN', '20', 'scanbugs'),
                ('i5', 'u4', 'lateral', '91', '20', 'ecdysis'),
                ('i6', 'u5', 'ventral', '0', '0', 'gbif'),
                ('i7', 'u6', 'dorsal', 'no coordinate', '20', 'gbif'),
                ('i8', NULL, '', '10', '20', NULL);
            CREATE TABLE gbif_meta (
                occurrenceID VARCHAR, institutionID VARCHAR, institutionCode VARCHAR
            );
            INSERT INTO gbif_meta VALUES
                ('u1', 'museum-a', 'MUSEUM'), ('u1', 'museum-a', 'MUSEUM'),
                ('u1', NULL, 'MUSEUM'), ('u2', 'museum-b', 'B'),
                ('u3', 'museum-a', 'MUSEUM'), ('u3', 'museum-b', 'B'),
                ('u4', NULL, NULL), ('u5', NULL, 'B');
            CREATE TABLE image_meta_taxonomy (
                img_id VARCHAR, input_taxon_key VARCHAR, update_status VARCHAR,
                match_method VARCHAR, accepted_family VARCHAR, accepted_species_name VARCHAR,
                accepted_rank VARCHAR, accepted_name VARCHAR
            );
            INSERT INTO image_meta_taxonomy VALUES
                ('i1', 't1', 'MATCHED', 'EXACT_ACCEPTED', 'Nymphalidae', 'Danaus plexippus',
                    'species', 'Danaus plexippus'),
                ('i2', 't1', 'MATCHED', 'EXACT_ACCEPTED', 'Nymphalidae', 'Danaus plexippus',
                    'species', 'Danaus plexippus'),
                ('i3', 't2', 'MATCHED', 'EXACT_SYNONYM', 'Nymphalidae', 'Danaus plexippus',
                    'subspecies', 'Danaus plexippus megalippe'),
                ('i4', 't3', 'AMBIGUOUS', 'AMBIGUOUS', 'Nymphalidae', 'Candidate name',
                    'species', 'Candidate name'),
                ('i5', 't4', 'UNMATCHED', 'UNMATCHED', NULL, NULL, NULL, NULL),
                ('i6', 't5', 'MATCHED', 'EXACT_CANONICAL', 'Pieridae', NULL,
                    'genus', 'Pieris'),
                ('i7', 't6', 'MATCHED', 'EXACT_ACCEPTED', 'Pieridae', NULL,
                    'species', 'Pieris rapae');
            CREATE TABLE col_taxonomy_matches AS
                SELECT DISTINCT input_taxon_key, update_status, match_method
                FROM image_meta_taxonomy;
            INSERT INTO col_taxonomy_matches VALUES ('unused', 'MATCHED', 'EXACT_ACCEPTED');
            CREATE TABLE image_meta_locality (
                img_id VARCHAR, locality VARCHAR, verbatim_locality VARCHAR
            );
            INSERT INTO image_meta_locality VALUES
                ('i1', 'Forest', NULL), ('i2', 'Forest', NULL), ('i3', '', ' Valley '),
                ('i4', '  ', ''), ('i5', NULL, NULL), ('i6', NULL, NULL), ('i7', NULL, NULL);
            ALTER TABLE image_meta_locality ADD COLUMN country_code VARCHAR;
            ALTER TABLE image_meta_locality ADD COLUMN country VARCHAR;
            UPDATE image_meta_locality SET country_code = CASE
                WHEN img_id IN ('i1', 'i2', 'i4', 'i6') THEN 'US'
                WHEN img_id = 'i3' THEN ' ca '
                WHEN img_id = 'i7' THEN 'ZZ' END;
            CREATE TABLE image_meta_coordinates (
                source_id VARCHAR, validation_status VARCHAR, country_check VARCHAR,
                latitude DOUBLE, longitude DOUBLE, reference_gid_0 VARCHAR,
                reference_country VARCHAR
            );
            INSERT INTO image_meta_coordinates VALUES
                ('i1', 'VALID', 'COUNTRY_MATCH', 40, -100, 'USA', 'United States'),
                ('i2', 'VALID', 'COUNTRY_MATCH', 40, -100, 'USA', 'United States'),
                ('i3', 'MISSING_COORDINATE', 'NOT_EVALUATED', 10, NULL, NULL, NULL),
                ('i4', 'MISSING_COORDINATE', 'NOT_EVALUATED', NULL, 20, NULL, NULL),
                ('i5', 'COORDINATE_OUT_OF_RANGE', 'NOT_EVALUATED', 91, 20, NULL, NULL),
                ('i6', 'ZERO_COORDINATE', 'NOT_EVALUATED', 0, 0, NULL, NULL),
                ('i7', 'MISSING_COORDINATE', 'NOT_EVALUATED', NULL, 20, NULL, NULL);
        """)
    return replace(load_settings(), database=database, output=tmp_path / "figures")
