"""Shared test fixtures for the BioCosmos backend tests."""

import polars as pl
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fake DuckDB client
# ---------------------------------------------------------------------------

class FakeDuckDBClient:
    """Minimal stand-in for DuckDBClient that avoids touching real databases."""

    def __init__(self):
        self.lock = MagicMock()
        self._tables: dict[str, pl.DataFrame] = {}

    # Context-manager protocol for self.lock
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query: str):
        return MagicMock(fetchone=lambda: (0,), pl=lambda: pl.DataFrame())

    def execute_query(self, query: str, params):
        return MagicMock(pl=lambda: pl.DataFrame())

    def execute_prepared(self, query: str, params: list):
        return MagicMock(pl=lambda: pl.DataFrame())

    def execute_prepared_to_pl(self, query: str, params: list) -> pl.DataFrame:
        return pl.DataFrame()

    def register(self, name: str, df: pl.DataFrame):
        self._tables[name] = df

    def unregister(self, name: str):
        self._tables.pop(name, None)

    def missing_tables(self, table_names: list[str]) -> list[str]:
        return [name for name in table_names if name not in self._tables]

    def table_exists(self, table_name: str) -> bool:
        return table_name in self._tables

    def column_exists(self, table_name: str, column_name: str) -> bool:
        table = self._tables.get(table_name)
        return table is not None and column_name in table.columns


# ---------------------------------------------------------------------------
# Fake LanceDB table
# ---------------------------------------------------------------------------

class FakeLanceSearch:
    """Chainable stand-in for a LanceDB search builder.

    A search result materializes to an eager Polars DataFrame, unlike a table
    (whose `to_polars` is lazy). `select`/`offset`/`limit` are honored so that
    projected, paged bulk reads can be exercised.
    """

    def __init__(self, data: pl.DataFrame):
        self._data = data
        self._offset = 0
        self._limit: int | None = None
        # Only meaningful once the vector column carries an ANN index, but the
        # builder accepts them either way and the code under test always sets
        # them.
        self.nprobes_value: int | None = None
        self.refine_factor_value: int | None = None

    def where(self, condition, prefilter=False):
        return self

    def distance_type(self, dtype):
        return self

    def nprobes(self, n):
        self.nprobes_value = n
        return self

    def refine_factor(self, n):
        self.refine_factor_value = n
        return self

    def select(self, columns):
        if columns:
            # A vector search keeps `_distance` even when it is not selected.
            keep = [*columns, *(c for c in ("_distance",) if c in self._data.columns)]
            self._data = self._data.select(list(dict.fromkeys(keep)))
        return self

    def offset(self, n):
        self._offset = n
        return self

    def limit(self, n):
        self._limit = n
        return self

    def to_polars(self):
        if self._offset == 0 and self._limit is None:
            return self._data
        return self._data.slice(self._offset, self._limit)

    def to_pydantic(self, model):
        return []


class FakeLanceTable:
    """Minimal stand-in for a LanceDB table."""

    def __init__(self, data: pl.DataFrame | None = None):
        self._data = data if data is not None else pl.DataFrame()

    def search(self, query=None, vector_column_name=None):
        return FakeLanceSearch(self._data)

    def to_polars(self):
        """Bulk reads off the table are lazy in the real LanceDB client."""
        return self._data.lazy()


class FakeLanceDB:
    """Minimal stand-in for the LanceDB wrapper."""

    def __init__(self, table: FakeLanceTable | None = None):
        self._table = table or FakeLanceTable()

    def create_or_get_collection(self, name: str):
        return self._table

    def count_entries(self, name: str):
        return self._table._data.height


# ---------------------------------------------------------------------------
# Fake FastAPI request
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_request():
    """Return a mock FastAPI Request whose app.state carries fake DB clients."""
    request = MagicMock()
    request.app.state.duck_db = FakeDuckDBClient()
    request.app.state.lance_db = FakeLanceDB()
    request.app.state.clip_embedder = MagicMock()
    request.app.state.unicom_embedder = MagicMock()
    return request


@pytest.fixture
def fake_duckdb():
    return FakeDuckDBClient()


@pytest.fixture
def fake_lance_table():
    return FakeLanceTable()


@pytest.fixture
def fake_lance_db():
    return FakeLanceDB()


# ---------------------------------------------------------------------------
# Real in-memory DuckDB client
# ---------------------------------------------------------------------------

class MemoryDuckDBClient:
    """A DuckDBClient-shaped wrapper around an in-memory database.

    FakeDuckDBClient returns empty frames, which is right for services whose
    SQL is incidental. The CoL ingest and the taxonomy update *are* their SQL,
    so they are tested against a real engine.
    """

    def __init__(self):
        import threading

        import duckdb

        self.conn = duckdb.connect()
        self.lock = threading.RLock()

    def execute(self, query: str):
        with self.lock:
            return self.conn.execute(query)

    def execute_query(self, query: str, params):
        with self.lock:
            return self.conn.execute(query, [params])

    def execute_prepared(self, query: str, params: list):
        with self.lock:
            return self.conn.execute(query, params)

    def execute_prepared_to_pl(self, query: str, params: list) -> pl.DataFrame:
        with self.lock:
            return self.conn.execute(query, params).pl()

    def register(self, name: str, df: pl.DataFrame):
        with self.lock:
            self.conn.register(name, df)

    def unregister(self, name: str):
        with self.lock:
            self.conn.unregister(name)

    def missing_tables(self, table_names: list[str]) -> list[str]:
        present = set(self.table_names())
        return [name for name in table_names if name not in present]

    def table_exists(self, table_name: str) -> bool:
        return not self.missing_tables([table_name])

    def column_exists(self, table_name: str, column_name: str) -> bool:
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = ? AND column_name = ?
                LIMIT 1
                """,
                [table_name, column_name],
            ).fetchall()
        return bool(rows)

    def table_type(self, table_name: str) -> str | None:
        with self.lock:
            row = self.conn.execute(
                "SELECT table_type FROM information_schema.tables "
                "WHERE table_name = ? LIMIT 1",
                [table_name],
            ).fetchone()
        return row[0] if row else None

    def create_or_replace_parquet(self, table_name: str, parquet_path: str):
        with self.lock:
            self.conn.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT * FROM read_parquet('{parquet_path}')"
            )

    def table_names(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT table_name FROM information_schema.tables ORDER BY table_name"
        ).fetchall()
        return [row[0] for row in rows]


@pytest.fixture
def memory_duckdb():
    client = MemoryDuckDBClient()
    yield client
    client.conn.close()


@pytest.fixture
def col_fixture_dir() -> str:
    """Directory holding the miniature ColDP release used by the CoL tests."""
    import os

    return os.path.join(os.path.dirname(__file__), "data", "col")
