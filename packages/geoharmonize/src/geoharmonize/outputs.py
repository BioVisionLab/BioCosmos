"""Coordinate-validation output artifacts."""

from __future__ import annotations

from harmonize_core.outputs import ArtifactRepository


class CoordinateOutputRepository(ArtifactRepository):
    """Create coordinate-validation artifacts atomically."""

    database_name = "coordinate_validation.duckdb"
    manifest_name = "coordinate_run.json"
    attach_alias = "geoharmonize_output"
