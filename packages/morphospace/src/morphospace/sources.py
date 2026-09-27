"""Read the image labels from DuckDB and stream the embeddings from LanceDB.

Both stores are opened read-only. The only link between them is `img_id`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
from harmonize_core.errors import SourceValidationError
from harmonize_core.identifiers import parse_table_identifier, qualified_name

# The images that count towards a species, grouped exactly as the backend's
# species, genus and family pages group them (`MATCHED_IMAGES` and
# `DOMINANT_RECORD` in backend/app/services/species_pages.py). A record the
# harmonizer resolved only to genus rank has no accepted species and is left
# out, as it is from every count on those pages.
#
# `page_key` is the recorded spelling most images of the species were filed
# under, the one its page is routed on. It is null when that spelling is not a
# binomial, because such a page cannot be reached by URL.
_LABELS = """
WITH matched AS (
    SELECT o.img_id,
           o.species AS recorded_key,
           lower(trim(o.class_dv)) AS side,
           t.accepted_species_name AS accepted_species,
           lower(split_part(t.accepted_name, ' ', 1)) AS genus_key,
           split_part(t.accepted_name, ' ', 1) AS genus_name,
           lower(t.accepted_family) AS family_key,
           t.accepted_family AS family_name
    FROM {image_meta} o
    JOIN {status} t USING (img_id)
    WHERE t.update_status = 'MATCHED'
      AND t.accepted_name IS NOT NULL
      AND t.accepted_species_name IS NOT NULL
      AND NOT list_contains(
          $exclude_families::VARCHAR[], coalesce(lower(trim(t.accepted_family)), '')
      )
), per_record AS (
    SELECT accepted_species,
           recorded_key,
           count(*) AS records,
           regexp_full_match(recorded_key, '[^\\s_()]+[\\s_]+[^\\s_()]+') AS is_binomial
    FROM matched
    GROUP BY accepted_species, recorded_key
), dominant AS (
    SELECT accepted_species, recorded_key, is_binomial
    FROM per_record
    QUALIFY row_number() OVER (
        PARTITION BY accepted_species
        ORDER BY is_binomial DESC, records DESC, recorded_key
    ) = 1
)
SELECT m.img_id,
       m.side,
       m.accepted_species,
       CASE WHEN d.is_binomial THEN d.recorded_key END AS page_key,
       m.genus_key,
       m.genus_name,
       m.family_key,
       m.family_name
FROM matched m
JOIN dominant d USING (accepted_species)
WHERE m.side IN ('dorsal', 'ventral')
"""

LABEL_COLUMNS = (
    "img_id",
    "side",
    "accepted_species",
    "page_key",
    "genus_key",
    "genus_name",
    "family_key",
    "family_name",
)


@dataclass(frozen=True)
class Labels:
    """One row per usable image, as parallel column arrays."""

    img_id: np.ndarray
    side: np.ndarray
    accepted_species: np.ndarray
    page_key: np.ndarray
    genus_key: np.ndarray
    genus_name: np.ndarray
    family_key: np.ndarray
    family_name: np.ndarray

    def __len__(self) -> int:
        return len(self.img_id)


def load_labels(
    database: Path,
    *,
    image_table: str = "image_meta",
    taxonomy_table: str = "image_meta_taxonomy",
    exclude_families: tuple[str, ...] = (),
) -> Labels:
    """Read the side and harmonized taxon of every image, read-only."""
    if not database.is_file():
        raise SourceValidationError(f"Database not found: {database}")
    query = _LABELS.format(
        image_meta=qualified_name(parse_table_identifier(image_table)),
        status=qualified_name(parse_table_identifier(taxonomy_table)),
    )
    try:
        connection = duckdb.connect(str(database), read_only=True)
    except duckdb.Error as exc:
        raise SourceValidationError(
            f"Cannot open {database} read-only. Stop the backend first: DuckDB allows a "
            "single writer, and a second process cannot attach while it holds the file."
        ) from exc
    try:
        excluded = sorted({name.strip().lower() for name in exclude_families if name.strip()})
        rows = connection.execute(query, {"exclude_families": excluded}).fetchnumpy()
    except duckdb.Error as exc:
        raise SourceValidationError(
            f"Cannot read labels from {image_table} and {taxonomy_table}: {exc}"
        ) from exc
    finally:
        connection.close()
    columns = {name: np.asarray(rows[name], dtype=object) for name in LABEL_COLUMNS}
    return Labels(**columns)


def open_embeddings(lance_dir: Path, table: str):
    """Open the LanceDB table holding the image embeddings."""
    import lancedb

    if not lance_dir.exists():
        raise SourceValidationError(f"LanceDB directory not found: {lance_dir}")
    try:
        return lancedb.connect(str(lance_dir)).open_table(table)
    except Exception as exc:  # lancedb raises bare ValueError/FileNotFoundError
        raise SourceValidationError(f"Cannot open LanceDB table {table!r}: {exc}") from exc


def table_version(lance_table) -> int | None:
    try:
        return int(lance_table.version)
    except Exception:  # pragma: no cover - older lancedb without versions
        return None


def iter_embeddings(
    lance_table,
    column: str,
    *,
    batch_size: int,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield `(img_ids, unit_vectors)` batches, re-normalized to unit length.

    The embedder normalizes on write, but the vectors went through float16 and
    an index; normalizing again costs nothing and makes every dot product a
    cosine similarity.
    """
    query = lance_table.search().select(["img_id", column]).limit(None)
    for batch in query.to_batches(batch_size):
        if batch.num_rows == 0:
            continue
        ids = np.asarray(batch.column("img_id").to_pylist(), dtype=object)
        values = batch.column(column)
        width = values.type.list_size
        vectors = (
            values.flatten().to_numpy(zero_copy_only=False).astype(np.float32).reshape(-1, width)
        )
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        valid = np.isfinite(norms[:, 0]) & (norms[:, 0] > 0)
        if not valid.all():
            ids, vectors, norms = ids[valid], vectors[valid], norms[valid]
        yield ids, vectors / norms
