"""Bring an existing LanceDB image collection up to the current layout.

Each step checks whether it is needed, so the migration is safe to re-run and
a dry run reports exactly what an applied run would do. In order:

1. Move the version manifests to the v2 naming scheme, which finds the latest
   version in one lookup instead of listing every manifest.
2. Add `img_path`, derived from `images.processed_dir` and `images.format` --
   the same path the embedder writes and the image routes read.
3. Optionally drop the legacy columns that stored each image's bytes in the
   table. Refused unless every image exists on disk, since those bytes are the
   only other copy.
4. Compact the many small fragments left by batched ingests.
5. Build a BTREE index on `img_id`, which every image lookup filters on.
6. Optionally rebuild existing vector indexes using the configured type.

Nothing here prunes the versions the migration creates: LanceDB keeps them for
seven days, so `table.restore(<starting version>)` undoes the run until then.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

from lancedb.background_loop import LOOP
from lancedb.index import BTree, IndexConfig
from lancedb.table import LanceTable, Table

from .lance import LEGACY_COLUMNS, vector_index_config

logger = logging.getLogger(__name__)

ID_COLUMN = "img_id"
PATH_COLUMN = "img_path"

# Vector index types, as `list_indices` names them. Each is also the name of
# its config class in `lancedb.index`.
VECTOR_INDEX_TYPES = (
    "IvfFlat",
    "IvfSq",
    "IvfPq",
    "IvfRq",
    "IvfHnswFlat",
    "IvfHnswSq",
    "IvfHnswPq",
)


# A step's description and the call that performs it.
Step = tuple[str, Callable[[], object]]


class MigrationError(RuntimeError):
    """A step found the collection unsafe to change."""


@dataclass
class MigrationReport:
    start_version: int
    applied: bool
    steps: list[str] = field(default_factory=list)


def migrate(
    table: Table,
    *,
    processed_dir: str,
    image_format: str,
    apply: bool = False,
    drop_legacy_columns: bool = False,
    reindex: bool = False,
    vector_type: str = "IvfPq",
) -> MigrationReport:
    """Run every needed step, or with `apply=False` only report them."""
    report = MigrationReport(start_version=int(table.version), applied=apply)
    steps = plan(
        table,
        processed_dir=processed_dir,
        image_format=image_format,
        drop_legacy_columns=drop_legacy_columns,
        reindex=reindex,
        vector_type=vector_type,
    )
    for description, action in steps:
        report.steps.append(description)
        if apply:
            logger.info("Migrating: %s", description)
            action()
    return report


def plan(
    table: Table,
    *,
    processed_dir: str,
    image_format: str,
    drop_legacy_columns: bool,
    reindex: bool,
    vector_type: str,
) -> list[Step]:
    """The steps `table` needs, in order, each with the call that performs it.

    Every check reads the table as it is now, before any step has run.
    """
    names = set(table.schema.names)
    legacy = [c for c in LEGACY_COLUMNS if c in names]
    # Checked before any step runs, so a refusal leaves the table untouched.
    if legacy and drop_legacy_columns:
        missing = _missing_images(table, processed_dir, image_format)
        if missing:
            raise MigrationError(
                f"{len(missing)} images are not on disk under {processed_dir} "
                f"(e.g. {', '.join(missing[:5])}); their bytes in "
                f"{', '.join(legacy)} are the only copy, so nothing was changed."
            )

    steps: list[Step] = []
    if not table.uses_v2_manifest_paths():
        steps.append(
            ("move manifests to v2 paths", partial(_migrate_manifest_paths, table))
        )

    if PATH_COLUMN not in names:
        expression = _path_expression(processed_dir, image_format)
        steps.append(
            (
                f"add column '{PATH_COLUMN}' = {expression}",
                partial(table.add_columns, {PATH_COLUMN: expression}),
            )
        )

    if legacy and drop_legacy_columns:
        steps.append(
            (
                f"drop legacy columns {', '.join(legacy)}",
                partial(table.drop_columns, legacy),
            )
        )

    small = _small_fragments(table)
    if small > 1:
        steps.append((f"compact {small} small fragments", table.optimize))

    indexes = list(table.list_indices())
    indexed = {c for index in indexes for c in (index.columns or [])}
    if ID_COLUMN not in indexed:
        steps.append(
            (
                f"build a BTREE index on '{ID_COLUMN}'",
                partial(table.create_index, ID_COLUMN, config=BTree()),
            )
        )

    if reindex:
        for index in indexes:
            if index.index_type not in VECTOR_INDEX_TYPES:
                continue
            (column,) = index.columns
            steps.append(
                (
                    f"rebuild {index.name} on '{column}' as {vector_type}",
                    partial(_retrain, table, index, column, vector_type),
                )
            )

    return steps


def _migrate_manifest_paths(table: Table) -> None:
    """Move a table's manifests to v2 paths.

    lancedb 0.39's `LanceTable.migrate_v2_manifest_paths` calls a method the
    async table does not have (it is `migrate_manifest_paths_v2` there), so the
    public call always raises. Go straight to the async method until upstream
    fixes the wrapper.
    """
    try:
        table.migrate_v2_manifest_paths()
    except AttributeError:
        if not isinstance(table, LanceTable):
            raise
        LOOP.run(table._table.migrate_manifest_paths_v2())


def _small_fragments(table: Table) -> int:
    """How many of the table's fragments are small enough to compact.

    lancedb annotates `stats()` as a dataclass but returns a plain dict.
    """
    stats = table.stats()
    if isinstance(stats, dict):
        return int(stats["fragment_stats"]["num_small_fragments"])
    return stats.fragment_stats.num_small_fragments


def _path_expression(processed_dir: str, image_format: str) -> str:
    prefix = os.path.join(processed_dir, "").replace("'", "''")
    suffix = f".{image_format}".replace("'", "''")
    return f"concat('{prefix}', {ID_COLUMN}, '{suffix}')"


def _missing_images(table: Table, processed_dir: str, image_format: str) -> list[str]:
    ids = table.search().select([ID_COLUMN]).limit(None).to_arrow()[ID_COLUMN]
    return [
        img_id
        for img_id in ids.to_pylist()
        if not os.path.exists(os.path.join(processed_dir, f"{img_id}.{image_format}"))
    ]


def _retrain(table: Table, index: IndexConfig, column: str, vector_type: str) -> None:
    """Replace one existing vector index using the configured type."""
    details = index.index_details or {}
    rows = table.count_rows()
    dims = table.schema.field(column).type.list_size
    config = vector_index_config(
        vector_type,
        rows=rows,
        dims=dims,
        metric=str(details.get("metric_type", "cosine")).lower(),
        details=details if index.index_type == vector_type else None,
    )
    table.create_index(column, config=config, replace=True, name=index.name)
