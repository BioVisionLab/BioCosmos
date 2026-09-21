"""Small, intentionally imperfect collection for publication regression checks."""

from dataclasses import replace

import duckdb
import pytest
from analyses.publication import load_settings


@pytest.fixture
def settings(tmp_path):
    database = tmp_path / "biocosmos.duckdb"
    with duckdb.connect(str(database)) as connection:
        connection.execute("""
            CREATE TABLE image_meta (
                img_id VARCHAR, uuid VARCHAR, class_dv VARCHAR, lat VARCHAR, lon VARCHAR
            );
            INSERT INTO image_meta VALUES
                ('i1', 'u1', 'dorsal', '10', '20'),
                ('i2', 'u1', 'ventral', '10', '20'),
                ('i3', 'u2', 'dorsal', '10', NULL),
                ('i4', 'u3', NULL, 'NaN', '20'),
                ('i5', 'u4', 'lateral', '91', '20'),
                ('i6', 'u5', 'ventral', '0', '0'),
                ('i7', 'u6', 'dorsal', 'no coordinate', '20'),
                ('i8', NULL, '', '10', '20');
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
            CREATE TABLE image_meta_coordinates (source_id VARCHAR, validation_status VARCHAR);
            INSERT INTO image_meta_coordinates VALUES
                ('i1', 'VALID'), ('i2', 'VALID'), ('i3', 'MISSING_COORDINATE'),
                ('i4', 'MISSING_COORDINATE'), ('i5', 'COORDINATE_OUT_OF_RANGE'),
                ('i6', 'ZERO_COORDINATE'), ('i7', 'MISSING_COORDINATE');
        """)
    return replace(load_settings(), database=database, output=tmp_path / "figures")
