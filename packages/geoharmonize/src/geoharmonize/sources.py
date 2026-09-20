"""Occurrence source adapter for coordinate validation."""

from __future__ import annotations

from harmonize_core.errors import SourceValidationError
from harmonize_core.sources import OccurrenceSource

from geoharmonize.models import CoordinateColumnMappings, CoordinateInspectionReport

COORDINATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "source_id": ("occurrenceID", "occurrence_id", "img_id", "id"),
    "latitude": ("decimalLatitude", "decimal_latitude", "latitude", "lat"),
    "longitude": ("decimalLongitude", "decimal_longitude", "longitude", "lon", "lng"),
    "country": ("countryCode", "country_code", "country"),
    "adm1": ("stateProvince", "state_province", "adm1", "state", "province"),
}


class CoordinateOccurrenceSource(OccurrenceSource):
    """Read-only access to an occurrence table and its georeference columns."""

    def resolve_coordinate_columns(
        self,
        available: dict[str, str],
        mappings: CoordinateColumnMappings,
        *,
        strict: bool = True,
    ) -> tuple[dict[str, str], list[str]]:
        """Resolve required coordinates and optional locality columns."""
        lower_names = self.index_by_casefold(available)
        resolved = {
            logical: self.resolve_requested(physical, available, lower_names)
            for logical, physical in mappings.as_logical_dict().items()
        }
        self.autodetect(resolved, COORDINATE_COLUMNS, lower_names)

        warnings: list[str] = []
        missing = [field for field in ("latitude", "longitude") if field not in resolved]
        if missing:
            warnings.append("Required coordinate columns were not found: " + ", ".join(missing))
        incompatible = self.incompatible_columns(resolved, available)
        if incompatible:
            warnings.append("Incompatible coordinate columns: " + ", ".join(incompatible))
        if strict and warnings:
            raise SourceValidationError(" ".join(warnings))
        return resolved, warnings

    def inspect(self, mappings: CoordinateColumnMappings) -> CoordinateInspectionReport:
        with self.connect() as connection:
            available = self.columns(connection)
            resolved, warnings = self.resolve_coordinate_columns(available, mappings, strict=False)
            point_columns = [
                resolved[field] for field in ("latitude", "longitude") if field in resolved
            ]
            row_count, distinct_count = self.count_rows_and_combinations(connection, point_columns)
        return CoordinateInspectionReport(
            database=self.database,
            table=self.identifier.display_name,
            row_count=row_count,
            distinct_point_count=distinct_count,
            detected_columns=resolved,
            available_columns=list(available),
            warnings=warnings,
            valid=not warnings,
        )
