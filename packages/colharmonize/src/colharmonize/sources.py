"""Occurrence and Catalogue of Life source adapters."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from harmonize_core.errors import SourceValidationError
from harmonize_core.sources import OccurrenceSource

from colharmonize.models import ColSourceInfo, ColumnMappings, InspectionReport

STANDARD_COLUMNS: dict[str, tuple[str, ...]] = {
    "genus": ("genus",),
    "specific_epithet": ("specificEpithet", "specific_epithet"),
    "infraspecific_epithet": ("infraspecificEpithet", "infraspecific_epithet"),
    "family": ("family",),
    "order": ("order",),
    "class": ("class",),
    "kingdom": ("kingdom",),
    "taxon_rank": ("taxonRank", "taxon_rank"),
    "authorship": ("scientificNameAuthorship", "scientific_name_authorship", "authorship"),
}
NAME_COLUMNS = ("scientificName", "species")


class TaxonOccurrenceSource(OccurrenceSource):
    """Read-only access to an occurrence table and its taxonomic columns."""

    def resolve_columns(
        self,
        available: dict[str, str],
        mappings: ColumnMappings,
        *,
        strict: bool = True,
    ) -> tuple[dict[str, str], list[str]]:
        lower_names = self.index_by_casefold(available)
        resolved: dict[str, str] = {}
        warnings: list[str] = []
        for logical, physical in mappings.as_logical_dict().items():
            resolved[logical] = self.resolve_requested(physical, available, lower_names)

        if "scientific_name" not in resolved:
            name_matches = [
                self.resolve_requested(name, available, lower_names)
                for name in NAME_COLUMNS
                if name.casefold() in lower_names
            ]
            name_matches = list(dict.fromkeys(name_matches))
            if len(name_matches) == 1:
                resolved["scientific_name"] = name_matches[0]
            elif len(name_matches) > 1:
                warnings.append(
                    "Both scientificName and species are present; map scientific_name explicitly."
                )

        self.autodetect(resolved, STANDARD_COLUMNS, lower_names)

        incompatible = self.incompatible_columns(resolved, available)
        if incompatible:
            warnings.append("Incompatible taxonomic columns: " + ", ".join(incompatible))

        has_name = "scientific_name" in resolved
        has_parts = "genus" in resolved and "specific_epithet" in resolved
        if not has_name and not has_parts:
            warnings.append(
                "A scientific-name column or both genus and specific epithet are required."
            )

        if strict and warnings:
            raise SourceValidationError(" ".join(warnings))
        return resolved, warnings

    def inspect(self, mappings: ColumnMappings) -> InspectionReport:
        with self.connect() as connection:
            available = self.columns(connection)
            resolved, warnings = self.resolve_columns(available, mappings, strict=False)
            row_count, distinct_count = self.count_rows_and_combinations(
                connection, list(resolved.values())
            )
        return InspectionReport(
            database=self.database,
            table=self.identifier.display_name,
            row_count=row_count,
            distinct_taxon_count=distinct_count,
            detected_columns=resolved,
            available_columns=list(available),
            warnings=warnings,
            valid=not warnings,
        )


class ColSource:
    """Validate and expose a combined ColDP NameUsage file."""

    SUPPORTED_SUFFIXES = {".tsv", ".tab", ".txt", ".csv"}

    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.is_file():
            raise SourceValidationError(f"Catalogue of Life source does not exist: {path}")

    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        with self.path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @contextmanager
    def materialize(self) -> Iterator[ColSourceInfo]:
        fingerprint = self.fingerprint()
        if self.path.suffix.casefold() in self.SUPPORTED_SUFFIXES:
            yield ColSourceInfo(
                source_path=self.path,
                data_path=self.path,
                fingerprint=fingerprint,
                delimiter="," if self.path.suffix.casefold() == ".csv" else "\t",
            )
            return
        if self.path.suffix.casefold() != ".zip":
            raise SourceValidationError(
                "Unsupported CoL input. Expected a ColDP ZIP or NameUsage TSV/TAB/TXT/CSV file."
            )

        with zipfile.ZipFile(self.path) as archive:
            candidates = [
                member
                for member in archive.namelist()
                if Path(member).suffix.casefold() in self.SUPPORTED_SUFFIXES
                and Path(member).stem.casefold().replace("-", "").replace("_", "") == "nameusage"
            ]
            if len(candidates) != 1:
                raise SourceValidationError(
                    "ColDP archive must contain exactly one NameUsage table; "
                    f"found {len(candidates)}."
                )
            member = candidates[0]
            suffix = Path(member).suffix.casefold()
            with tempfile.TemporaryDirectory(prefix="colharmonize-") as directory:
                extracted = Path(directory) / f"NameUsage{suffix}"
                with archive.open(member) as source, extracted.open("wb") as target:
                    shutil.copyfileobj(source, target)
                yield ColSourceInfo(
                    source_path=self.path,
                    data_path=extracted,
                    fingerprint=fingerprint,
                    delimiter="," if suffix == ".csv" else "\t",
                    archive_member=member,
                )
