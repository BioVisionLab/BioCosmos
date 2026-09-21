"""Atomic creation of run artifacts and their JSON manifest."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb
from pydantic import BaseModel

from harmonize_core.errors import OutputError
from harmonize_core.models import ArtifactDigest

_HASH_BLOCK = 1024 * 1024


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file, read in fixed-size blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(_HASH_BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def describe_artifact(role: str, path: Path) -> ArtifactDigest:
    """Digest a finished artifact so a consumer can detect changes to it."""
    resolved = path.resolve()
    return ArtifactDigest(
        role=role,
        path=resolved,
        bytes=resolved.stat().st_size,
        sha256=file_sha256(resolved),
    )


def write_json_atomically(destination: Path, payload: dict[str, object]) -> Path:
    """Write JSON deterministically through a temporary file in the same directory."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, destination)
    return destination


class ArtifactRepository:
    """Create one run's DuckDB output and manifest without partial writes.

    Subclasses supply the artifact filenames and the DuckDB attach alias used
    when copying results back into a source database.
    """

    database_name: str = "output.duckdb"
    manifest_name: str = "run.json"
    attach_alias: str = "harmonize_output"

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.database_path = output_dir / self.database_name
        self.manifest_path = output_dir / self.manifest_name

    @contextmanager
    def build_database(self, *, force: bool) -> Iterator[duckdb.DuckDBPyConnection]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.database_path.exists() and not force:
            raise OutputError(f"Output database already exists: {self.database_path}")
        temporary = self.output_dir / f".{self.database_name}.{uuid.uuid4().hex}.tmp"
        connection = duckdb.connect(str(temporary))
        try:
            yield connection
            connection.execute("CHECKPOINT")
            connection.close()
            os.replace(temporary, self.database_path)
        except Exception:
            connection.close()
            temporary.unlink(missing_ok=True)
            raise

    def write_manifest(self, manifest: BaseModel, *, force: bool) -> Path:
        if self.manifest_path.exists() and not force:
            raise OutputError(f"Manifest already exists: {self.manifest_path}")
        return write_json_atomically(self.manifest_path, manifest.model_dump(mode="json"))
