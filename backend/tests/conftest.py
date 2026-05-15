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


# ---------------------------------------------------------------------------
# Fake LanceDB table
# ---------------------------------------------------------------------------

class FakeLanceTable:
    """Minimal stand-in for a LanceDB table."""

    def __init__(self, data: pl.DataFrame | None = None):
        self._data = data if data is not None else pl.DataFrame()

    def search(self, query=None, vector_column_name=None):
        return self

    def where(self, condition, prefilter=False):
        return self

    def distance_type(self, dtype):
        return self

    def limit(self, n):
        return self

    def to_polars(self):
        return self._data

    def to_pydantic(self, model):
        return []


class FakeLanceDB:
    """Minimal stand-in for the LanceDB wrapper."""

    def __init__(self, table: FakeLanceTable | None = None):
        self._table = table or FakeLanceTable()

    def create_or_get_collection(self, name: str):
        return self._table

    def count_entries(self, name: str):
        return 0


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
