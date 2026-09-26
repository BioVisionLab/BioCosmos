import logging

import duckdb
import polars as pl
import threading

from ..configs.config import get_duck_db_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def family_kept_sql(column: str, families: list[str]) -> str:
    """A predicate true when `column` is not one of the excluded `families`.

    `families` are already lowercased and trimmed (ImageMetaConfig does it).
    DDL takes no parameters, so the names are inlined as escaped literals.
    """
    if not families:
        return "TRUE"
    literals = ", ".join("'" + name.replace("'", "''") + "'" for name in families)
    return f"({column} IS NULL OR lower(trim({column})) NOT IN ({literals}))"


class DuckDBClient:
    """
    A simple DuckDB client wrapper.
    """

    def __init__(self):
        db_path = get_duck_db_path()
        self.conn = duckdb.connect(database=str(db_path))
        # No fts extension: nothing in this codebase runs a BM25 query. An
        # existing biocosmos.duckdb still carries fts_main_image_meta and
        # fts_main_gbif_meta schemas from when it did, but they are inert --
        # the file opens and queries fine without the extension loaded.
        self.lock = threading.RLock()
        logger.info(f"DuckDB connected at {db_path}")

    def register(self, name: str, df: pl.DataFrame):
        """Register a Polars DataFrame as a DuckDB table.
        Args:
            name (str): The name of the table.
            df (pl.DataFrame): The Polars DataFrame to register.
        """
        with self.lock:
            self.conn.register(name, df)
        logger.info(f"DataFrame registered as table '{name}'.")

    def unregister(self, name: str):
        """Unregister a DuckDB table.
        Args:
            name (str): The name of the table to unregister.
        """
        with self.lock:
            self.conn.unregister(name)
        logger.info(f"Table '{name}' unregistered.")

    def execute(self, query: str):
        """Execute a SQL query and return the result.
        Args:
            query (str): The SQL query to execute.
        Returns:
            duckdb.DuckDBPyRelation: The result of the query.
        """
        with self.lock:
            return self.conn.execute(query)

    def execute_query(self, query: str, params: str):
        """Execute a SQL query with parameters.
        Args:
            query (str): The SQL query to execute.
            params (str): The parameter to bind to the query.
        Returns:
            duckdb.DuckDBPyRelation: The result of the query.
        """
        with self.lock:
            return self.conn.execute(query, [params])

    def execute_prepared(self, query: str, params: list):
        """Execute a prepared SQL query with parameters.
        Args:
            query (str): The SQL query to execute.
            params (list): The list of parameters to bind to the query.
        Returns:
            duckdb.DuckDBPyRelation: The result of the query.
        """
        with self.lock:
            return self.conn.execute(query, params)

    def execute_prepared_to_pl(self, query: str, params: list) -> pl.DataFrame:
        """Execute a prepared SQL query with parameters and return the result as a Polars DataFrame.
        Args:
            query (str): The SQL query to execute.
            params (list): The list of parameters to bind to the query.
        Returns:
            pl.DataFrame: The result of the query as a Polars DataFrame.
        """
        with self.lock:
            return self.conn.execute(query, params).pl()

    def create_or_replace_table_csv(self, table_name: str, csv_path: str):
        """Create or replace a table from a CSV file.
        Args:
            table_name (str): The name of the table to create or replace.
            csv_path (str): The path to the CSV file.
        """
        logger.info(f"Creating '{table_name}' from '{csv_path}'.")
        self.conn.execute(
            f"""
            CREATE OR REPLACE TABLE {table_name} AS 
            SELECT * FROM read_csv_auto('{csv_path}')
            """
        )
        logger.info(f"Table '{table_name}' created or replaced.")

    def create_or_replace_parquet(self, table_name: str, parquet_path: str):
        """Create or replace a table from a Parquet file.
        Args:
            table_name (str): The name of the table to create or replace.
            parquet_path (str): The path to the Parquet file.
        """
        logger.info(f"Creating '{table_name}' from '{parquet_path}'.")
        self.conn.execute(
            f"""
            CREATE OR REPLACE TABLE {table_name} AS 
            SELECT * FROM read_parquet('{parquet_path}')
            """
        )
        logger.info(f"Table '{table_name}' created or replaced.")
    
    def create_if_not_exists_parquet(self, table_name: str, parquet_path: str):
        """Create a table from a Parquet file if it does not exist.
        Args:
            table_name (str): The name of the table to create.
            parquet_path (str): The path to the Parquet file.
        """
        logger.info(f"Creating '{table_name}' from '{parquet_path}'.")
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} AS 
            SELECT * FROM read_parquet('{parquet_path}')
            """
        )
        logger.info(f"Table '{table_name}' created or already exists.")

    def create_if_not_exists_csv(self, table_name: str, csv_path: str):
        """Create a table from a CSV file if it does not exist.
        Args:
            table_name (str): The name of the table to create.
            csv_path (str): The path to the CSV file.
        """
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} AS 
            SELECT * FROM read_csv_auto('{csv_path}')
            """
        )
        logger.info(f"Table '{table_name}' created or already exists.")

    def create_if_not_exists_pl(self, table_name: str, df: pl.DataFrame):
        """Create a table from a Polars DataFrame if it does not exist.
        Args:
            table_name (str): The name of the table to create.
            df (pl.DataFrame): The Polars DataFrame to use.
        """
        self.conn.register("df", df)
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} AS 
            SELECT * FROM df
            """
        )
        logger.info(f"Table '{table_name}' created or already exists.")

    def missing_tables(self, table_names: list[str]) -> list[str]:
        """Return the names among ``table_names`` that do not exist.

        Ingestion is guarded by `skip` flags and by the presence of source
        files, so several services have to ask whether a table was actually
        built before querying it. Asking is cheaper, and gives a far better
        error, than letting DuckDB raise a catalog error per query.
        """
        if not table_names:
            return []
        placeholders = ", ".join("?" for _ in table_names)
        try:
            with self.lock:
                rows = self.conn.execute(
                    f"""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_name IN ({placeholders})
                    """,
                    list(table_names),
                ).fetchall()
        except duckdb.Error as error:
            logger.warning(f"Could not check for tables {table_names}: {error}")
            return list(table_names)
        present = {row[0] for row in rows}
        return [name for name in table_names if name not in present]

    def table_type(self, table_name: str) -> str | None:
        """'BASE TABLE', 'VIEW', or None when no such object exists."""
        with self.lock:
            row = self.conn.execute(
                """
                SELECT table_type FROM information_schema.tables
                WHERE table_name = ?
                LIMIT 1
                """,
                [table_name],
            ).fetchone()
        return row[0] if row else None

    def table_exists(self, table_name: str) -> bool:
        """Whether a table has been created in this database."""
        return not self.missing_tables([table_name])

    def column_exists(self, table_name: str, column_name: str) -> bool:
        """Whether a table carries a given column.

        Ingestion can be skipped and an existing database is not re-ingested,
        so a column the current code expects may simply not be there. Asking
        lets a projection fall back to NULL rather than failing the whole
        statement. Unlike `missing_tables`, the conservative answer here is
        False: treating an unknown column as absent degrades, treating it as
        present would raise.
        """
        try:
            with self.lock:
                rows = self.conn.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = ? AND column_name = ?
                    LIMIT 1
                    """,
                    [table_name, column_name],
                ).fetchall()
        except duckdb.Error as error:
            logger.warning(
                f"Could not check for column '{table_name}.{column_name}': {error}"
            )
            return False
        return bool(rows)

    def fetchdf(self):
        """Fetch the result of the last query as a Polars DataFrame.
        Returns:
            pl.DataFrame: The result of the query as a Polars DataFrame.
        """
        return self.conn.fetchdf()

    def close(self):
        """Close the DuckDB connection."""
        self.conn.close()
        logger.info("DuckDB connection closed.")
