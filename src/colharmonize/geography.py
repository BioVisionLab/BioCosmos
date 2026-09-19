"""Read the relevant subset of a GADM GeoPackage safely and efficiently."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from shapely import from_wkb, make_valid
from shapely.geometry.base import BaseGeometry

from colharmonize.errors import SourceValidationError
from colharmonize.models import GadmSourceInfo


def _quote_sqlite_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _gpkg_wkb(blob: bytes) -> bytes:
    """Remove the GeoPackage binary header and return ordinary WKB."""
    if len(blob) < 8 or blob[:2] != b"GP":
        raise SourceValidationError("GADM geometry is not a valid GeoPackage geometry blob")
    flags = blob[3]
    envelope_code = (flags >> 1) & 0b111
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    if envelope_code not in envelope_sizes:
        raise SourceValidationError("GADM geometry uses an unsupported GeoPackage envelope")
    header_size = 8 + envelope_sizes[envelope_code]
    if len(blob) <= header_size:
        raise SourceValidationError("GADM geometry contains no WKB payload")
    return blob[header_size:]


@dataclass(frozen=True)
class GadmFeature:
    """One administrative feature selected by the GeoPackage R-tree."""

    feature_id: str
    gid0: str
    country: str
    gid1: str
    adm1: str
    geometry_blob: bytes
    geometry: BaseGeometry
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class GadmSource:
    """Validate a GADM GeoPackage and load only features near occupied tiles."""

    REQUIRED_FIELDS = ("GID_0", "COUNTRY", "GID_1", "NAME_1")

    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.is_file():
            raise SourceValidationError(f"GADM GeoPackage does not exist: {path}")

    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        with self.path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        uri = self.path.resolve().as_uri() + "?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            yield connection
        except sqlite3.DatabaseError as exc:
            raise SourceValidationError(f"Invalid GADM GeoPackage: {self.path}: {exc}") from exc
        finally:
            if "connection" in locals():
                connection.close()

    def inspect(self, layer: str | None = None) -> GadmSourceInfo:
        """Select an ADM1 polygon layer and validate its spatial index."""
        with self.connect() as connection:
            try:
                geometry_rows = connection.execute(
                    """
                    SELECT table_name, column_name, geometry_type_name, srs_id
                    FROM gpkg_geometry_columns
                    """
                ).fetchall()
            except sqlite3.DatabaseError as exc:
                raise SourceValidationError(
                    "GADM input is missing the GeoPackage geometry catalog"
                ) from exc

            candidates: list[tuple[sqlite3.Row, dict[str, tuple[str, str, int]]]] = []
            for row in geometry_rows:
                if str(row["geometry_type_name"]).upper() not in {"POLYGON", "MULTIPOLYGON"}:
                    continue
                columns = self._table_columns(connection, str(row["table_name"]))
                by_casefold = {name.casefold(): details for name, details in columns.items()}
                if all(field.casefold() in by_casefold for field in self.REQUIRED_FIELDS):
                    candidates.append((row, columns))

            selected = self._select_layer(candidates, layer)
            row, columns = selected
            table_name = str(row["table_name"])
            geometry_column = str(row["column_name"])
            srs_id = int(row["srs_id"])
            if srs_id != 4326:
                raise SourceValidationError(
                    f"GADM layer {table_name} must use EPSG:4326; found SRS {srs_id}"
                )

            primary_keys = [
                (name, details)
                for name, details in columns.items()
                if details[2] > 0 and "INT" in details[1].upper()
            ]
            if len(primary_keys) != 1:
                raise SourceValidationError(
                    f"GADM layer {table_name} must have one integer primary key"
                )
            feature_id_column = primary_keys[0][0]
            rtree_name = f"rtree_{table_name}_{geometry_column}"
            rtree_row = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND lower(name) = lower(?)",
                [rtree_name],
            ).fetchone()
            if rtree_row is None:
                raise SourceValidationError(
                    f"GADM layer {table_name} has no GeoPackage R-tree for {geometry_column}"
                )

            resolved = {
                field: next(name for name in columns if name.casefold() == field.casefold())
                for field in self.REQUIRED_FIELDS
            }

        return GadmSourceInfo(
            path=self.path,
            fingerprint=self.fingerprint(),
            layer=table_name,
            geometry_column=geometry_column,
            feature_id_column=feature_id_column,
            gid0_column=resolved["GID_0"],
            country_column=resolved["COUNTRY"],
            gid1_column=resolved["GID_1"],
            adm1_column=resolved["NAME_1"],
            srs_id=srs_id,
        )

    def load_features(
        self,
        info: GadmSourceInfo,
        tile_bounds: Sequence[tuple[float, float, float, float]],
        *,
        buffer: float,
    ) -> list[GadmFeature]:
        """Load and decode features whose R-tree bounds overlap occupied tiles."""
        if not tile_bounds:
            return []
        table = _quote_sqlite_identifier(info.layer)
        geometry = _quote_sqlite_identifier(info.geometry_column)
        feature_id = _quote_sqlite_identifier(info.feature_id_column)
        gid0 = _quote_sqlite_identifier(info.gid0_column)
        country = _quote_sqlite_identifier(info.country_column)
        gid1 = _quote_sqlite_identifier(info.gid1_column)
        adm1 = _quote_sqlite_identifier(info.adm1_column)
        rtree = _quote_sqlite_identifier(f"rtree_{info.layer}_{info.geometry_column}")
        selected: dict[str, GadmFeature] = {}

        with self.connect() as connection:
            for offset in range(0, len(tile_bounds), 100):
                batch = tile_bounds[offset : offset + 100]
                predicates: list[str] = []
                parameters: list[float] = []
                for min_x, min_y, max_x, max_y in batch:
                    predicates.append(
                        "(r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?)"
                    )
                    parameters.extend(
                        [max_x + buffer, min_x - buffer, max_y + buffer, min_y - buffer]
                    )
                rows = connection.execute(
                    f"""
                    SELECT CAST(f.{feature_id} AS TEXT) AS feature_id,
                           CAST(f.{gid0} AS TEXT) AS gid0,
                           CAST(f.{country} AS TEXT) AS country,
                           CAST(f.{gid1} AS TEXT) AS gid1,
                           CAST(f.{adm1} AS TEXT) AS adm1,
                           f.{geometry} AS geometry,
                           r.minx, r.maxx, r.miny, r.maxy
                    FROM {table} AS f
                    JOIN {rtree} AS r ON r.id = f.{feature_id}
                    WHERE {' OR '.join(predicates)}
                    """,
                    parameters,
                ).fetchall()
                for row in rows:
                    key = str(row["feature_id"])
                    if key in selected:
                        continue
                    geometry_blob = bytes(row["geometry"])
                    try:
                        decoded = from_wkb(_gpkg_wkb(geometry_blob))
                        if not decoded.is_valid:
                            decoded = make_valid(decoded)
                    except Exception as exc:
                        raise SourceValidationError(
                            f"Could not decode geometry {key} in GADM layer {info.layer}: {exc}"
                        ) from exc
                    if decoded.is_empty:
                        continue
                    selected[key] = GadmFeature(
                        feature_id=key,
                        gid0=str(row["gid0"] or ""),
                        country=str(row["country"] or ""),
                        gid1=str(row["gid1"] or ""),
                        adm1=str(row["adm1"] or ""),
                        geometry_blob=geometry_blob,
                        geometry=decoded,
                        min_x=float(row["minx"]),
                        max_x=float(row["maxx"]),
                        min_y=float(row["miny"]),
                        max_y=float(row["maxy"]),
                    )
        return list(selected.values())

    @staticmethod
    def _table_columns(
        connection: sqlite3.Connection, table: str
    ) -> dict[str, tuple[str, str, int]]:
        rows = connection.execute(
            f"PRAGMA table_info({_quote_sqlite_identifier(table)})"
        ).fetchall()
        return {
            str(row["name"]): (str(row["name"]), str(row["type"] or ""), int(row["pk"]))
            for row in rows
        }

    @staticmethod
    def _select_layer(
        candidates: list[tuple[sqlite3.Row, dict[str, tuple[str, str, int]]]],
        requested: str | None,
    ) -> tuple[sqlite3.Row, dict[str, tuple[str, str, int]]]:
        if requested is not None:
            matches = [item for item in candidates if str(item[0]["table_name"]) == requested]
            if not matches:
                matches = [
                    item
                    for item in candidates
                    if str(item[0]["table_name"]).casefold() == requested.casefold()
                ]
            if len(matches) != 1:
                raise SourceValidationError(
                    f"GADM layer {requested!r} was not found or lacks ADM1 fields"
                )
            return matches[0]

        preferred = [
            item
            for item in candidates
            if re.search(r"(?:^|_)adm_?1$", str(item[0]["table_name"]), re.IGNORECASE)
        ]
        if len(preferred) == 1:
            return preferred[0]
        if len(candidates) == 1:
            return candidates[0]
        names = ", ".join(sorted(str(item[0]["table_name"]) for item in candidates)) or "none"
        raise SourceValidationError(
            "Could not select one GADM ADM1 layer automatically. "
            f"Available compatible layers: {names}. Supply --gadm-layer."
        )
