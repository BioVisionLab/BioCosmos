"""Input and output shapes for institution resolution."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class MatchSource(StrEnum):
    """Where a resolved name came from, strongest evidence first."""

    # A hand-checked entry in the override file.
    CURATED = "curated"
    # The data already carries a full name in the code field.
    VERBATIM = "verbatim"
    # GRSciColl matched on an identifier or a dataset-scoped code.
    GRSCICOLL_EXACT = "grscicoll_exact"
    # GRSciColl matched the code only, and the name agrees with the publisher.
    GRSCICOLL_VERIFIED = "grscicoll_verified"
    # The GBIF publishing organization, whose name spells out the code.
    GBIF_PUBLISHER = "gbif_publisher"
    UNRESOLVED = "unresolved"


class InstitutionRecord(BaseModel):
    """One (institution code, dataset) combination seen in occurrence data.

    Field names follow Darwin Core and the GBIF occurrence download, in
    snake_case. `occurrences` weighs combinations when one code appears in
    several datasets: the most common one is tried first.
    """

    model_config = ConfigDict(frozen=True)

    institution_code: str
    dataset_key: str | None = None
    institution_id: str | None = None
    owner_institution_code: str | None = None
    publisher: str | None = None
    publishing_country: str | None = None
    occurrences: int = 0


class Institution(BaseModel):
    """The resolved institution behind one code."""

    code: str
    name: str | None = None
    homepage: str | None = None
    country: str | None = None
    grscicoll_key: str | None = None
    source: MatchSource = MatchSource.UNRESOLVED
    # True when resolution failed on a registry error rather than on evidence,
    # so a caller that caches results should try the code again later.
    retry: bool = False

    @property
    def resolved(self) -> bool:
        return self.name is not None
