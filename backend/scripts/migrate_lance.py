"""
Migrate the LanceDB image collection to the current layout.

Dry run by default: prints the steps an applied run would take. Stop the
backend before applying -- a running API keeps reading the version it opened.
See `app/database/lance_migration.py` for what each step does.

Usage:
    cd backend
    uv run --env-file .env python scripts/migrate_lance.py
    uv run --env-file .env python scripts/migrate_lance.py --apply
    uv run --env-file .env python scripts/migrate_lance.py --apply --drop-legacy-columns --reindex
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lancedb

from app.configs.config import ImageConfig, SearchIndexConfig, get_lance_db_path
from app.database.lance_migration import MigrationError, migrate


def main():
    config = ImageConfig()
    parser = argparse.ArgumentParser(
        description="Migrate the LanceDB image collection to the current layout."
    )
    parser.add_argument("--db", default=get_lance_db_path(), help="LanceDB path")
    parser.add_argument("--table", default=config.table)
    parser.add_argument("--apply", action="store_true", help="make the changes")
    parser.add_argument(
        "--drop-legacy-columns",
        action="store_true",
        help="drop the stored image bytes (only if every image is on disk)",
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="rebuild existing vector indexes using search_index.vector_type",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    table = lancedb.connect(args.db).open_table(args.table)
    try:
        report = migrate(
            table,
            processed_dir=config.processed_dir,
            image_format=config.format,
            apply=args.apply,
            drop_legacy_columns=args.drop_legacy_columns,
            reindex=args.reindex,
            vector_type=SearchIndexConfig().vector_type,
        )
    except MigrationError as error:
        print(f"Refused: {error}", file=sys.stderr)
        return 1

    verb = "Applied" if report.applied else "Would apply"
    print(f"{args.db}/{args.table} at version {report.start_version}")
    if not report.steps:
        print("Already up to date.")
    print(f"{verb}:")
    for step in report.steps:
        print(f"  - {step}")
    if report.applied:
        print(f"Undo within seven days with table.restore({report.start_version}).")
    else:
        print("Re-run with --apply to make these changes.")


if __name__ == "__main__":
    sys.exit(main())
