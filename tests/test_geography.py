from pathlib import Path

import pytest

from colharmonize.errors import SourceValidationError
from colharmonize.geography import GadmSource


def test_gadm_layer_and_rtree_are_discovered(gadm_gpkg: Path) -> None:
    source = GadmSource(gadm_gpkg)
    info = source.inspect()
    assert info.layer == "ADM_ADM_1"
    assert info.geometry_column == "geom"
    assert info.feature_id_column == "fid"
    assert info.srs_id == 4326
    assert len(info.fingerprint) == 64

    features = source.load_features(info, [(0, 0, 10, 10)], buffer=0.001)
    assert {feature.feature_id for feature in features} == {"1", "3"}
    assert all(not feature.geometry.is_empty for feature in features)


def test_requested_missing_gadm_layer_is_rejected(gadm_gpkg: Path) -> None:
    with pytest.raises(SourceValidationError, match="was not found"):
        GadmSource(gadm_gpkg).inspect("missing_layer")
