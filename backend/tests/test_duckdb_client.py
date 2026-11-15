"""DuckDBClient runs each thread's queries on that thread's own cursor."""

import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import duckdb
import polars as pl
import pytest

from app.database.duckdb import DuckDBClient

CONFIG = {"db": {"duck": {"file": "test.duckdb", "threads": 2}, "lance": {}}}


@pytest.fixture
def duck_db(tmp_path, monkeypatch) -> Iterator[DuckDBClient]:
    monkeypatch.setenv("DUCK_DIR", str(tmp_path))

    with patch("app.configs.config.load_config", return_value=CONFIG):
        client = DuckDBClient()

    client.conn.execute("CREATE TABLE numbers AS SELECT range AS n FROM range(100)")

    yield client

    client.close()


def _query_then_fetch(duck_db: DuckDBClient, barrier: threading.Barrier, n: int) -> int:
    result = duck_db.execute_query("SELECT n FROM numbers WHERE n = ?", str(n))
    # Every thread has run its query before any thread fetches. On a shared
    # connection each fetch would read the last query to run.
    barrier.wait()
    row = result.fetchone()

    assert row is not None

    return row[0]


def test_each_thread_fetches_its_own_result(duck_db):
    workers = 8
    barrier = threading.Barrier(workers)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_query_then_fetch, duck_db, barrier, n) for n in range(workers)
        ]
        results = [future.result(timeout=10) for future in futures]

    assert results == list(range(workers))


def test_registered_frame_is_private_to_its_thread(duck_db):
    duck_db.register("private_frame", pl.DataFrame({"n": [1]}))

    assert duck_db.execute_to_pl("SELECT n FROM private_frame")["n"].to_list() == [1]

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(duck_db.execute_to_pl, "SELECT n FROM private_frame")

        with pytest.raises(duckdb.CatalogException):
            future.result(timeout=10)


def _count_into(duck_db: DuckDBClient, counts: list[int]) -> None:
    frame = duck_db.execute_to_pl("SELECT count(*) AS c FROM numbers")
    counts.extend(frame["c"].to_list())


def test_reads_do_not_wait_for_the_write_lock(duck_db):
    counts: list[int] = []
    # A daemon thread, so a read stuck behind the lock fails the test rather
    # than hanging it at shutdown.
    reader = threading.Thread(target=_count_into, args=(duck_db, counts), daemon=True)

    with duck_db.lock:
        reader.start()
        reader.join(timeout=10)

    assert counts == [100]


def test_cursors_see_tables_written_through_the_root_connection(duck_db):
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(duck_db.execute, "SELECT 1").result(timeout=10)
        duck_db.conn.execute("CREATE TABLE later AS SELECT 7 AS n")
        frame = pool.submit(duck_db.execute_to_pl, "SELECT n FROM later").result(
            timeout=10
        )

    assert frame["n"].to_list() == [7]


def test_close_closes_every_cursor(tmp_path, monkeypatch):
    monkeypatch.setenv("DUCK_DIR", str(tmp_path))

    with patch("app.configs.config.load_config", return_value=CONFIG):
        client = DuckDBClient()

    cursor = client.cursor
    client.close()

    with pytest.raises(duckdb.ConnectionException):
        cursor.execute("SELECT 1")
