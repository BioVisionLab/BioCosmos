"""Run parameters, manifest and write-back report."""

from __future__ import annotations

from typing import Literal

from harmonize_core.models import ArtifactDigest, FrozenModel
from pydantic import Field

SIDES: tuple[str, ...] = ("dorsal", "ventral")

ScopeRank = Literal["all", "family", "genus"]


class MorphospaceParameters(FrozenModel):
    """Every knob that changes the numbers a run produces."""

    embedding_column: str = "unicom_embeddings"
    min_images: int = Field(default=3, ge=1)
    min_scope_species: int = Field(default=3, ge=2)
    rarefy_k: int = Field(default=5, ge=2)
    bootstrap: int = Field(default=200, ge=1)
    mantel_min_species: int = Field(default=5, ge=3)
    mantel_max_species: int = Field(default=5000, ge=3)
    permutations: int = Field(default=999, ge=0)
    permutation_max_species: int = Field(default=2000, ge=3)
    batch_size: int = Field(default=50_000, ge=1)
    seed: int = 42
    # Harmonized families left out of every morphospace, lowercased on read.
    # Castniidae are moths imaged with the butterflies.
    exclude_families: tuple[str, ...] = ("Castniidae",)


class MorphospaceRunManifest(FrozenModel):
    """Provenance, outputs, timing and counts for one run."""

    schema_version: int = 1
    run_id: str
    package_version: str
    started_at: str
    completed_at: str
    runtime_seconds: float
    source_database: str
    lance_database: str
    lance_table: str
    lance_version: int | None
    parameters: MorphospaceParameters
    outputs: dict[str, str]
    artifacts: list[ArtifactDigest] = Field(default_factory=list)
    counts: dict[str, int]


class WriteBackReport(FrozenModel):
    """What `integrate` copied into the backend database."""

    tables: dict[str, int]
