from ..configs.config import get_duck_db_path
import duckdb
import logging
import polars as pl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DuckDBClient:
    """
    A simple DuckDB client wrapper.
    """

    def __init__(self):
        db_path = get_duck_db_path()
        self.conn = duckdb.connect(database=str(db_path))
        logger.info(f"DuckDB connected at {db_path}")

    def register(self, name: str, df: pl.DataFrame):
        """Register a Polars DataFrame as a DuckDB table.
        Args:
            name (str): The name of the table.
            df (pl.DataFrame): The Polars DataFrame to register.
        """
        self.conn.register(name, df)
        logger.info(f"DataFrame registered as table '{name}'.")

    def unregister(self, name: str):
        """Unregister a DuckDB table.
        Args:
            name (str): The name of the table to unregister.
        """
        self.conn.unregister(name)
        logger.info(f"Table '{name}' unregistered.")

    def execute(self, query: str):
        """Execute a SQL query and return the result.
        Args:
            query (str): The SQL query to execute.
        Returns:
            duckdb.DuckDBPyRelation: The result of the query.
        """
        return self.conn.execute(query)

    def execute_query(self, query: str, params: str):
        """Execute a SQL query with parameters.
        Args:
            query (str): The SQL query to execute.
            params (str): The parameter to bind to the query.
        Returns:
            duckdb.DuckDBPyRelation: The result of the query.
        """
        return self.conn.execute(query, [params])

    def execute_prepared(self, query: str, params: list):
        """Execute a prepared SQL query with parameters.
        Args:
            query (str): The SQL query to execute.
            params (list): The list of parameters to bind to the query.
        Returns:
            duckdb.DuckDBPyRelation: The result of the query.
        """
        return self.conn.execute(query, params)

    def create_or_replace_table_csv(
        self, table_name: str, csv_path: str
    ):
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

    def create_if_not_exists_csv(
        self, table_name: str, csv_path: str
    ):
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
        logger.info(
            f"Table '{table_name}' created or already exists."
        )

    def create_if_not_exists_pl(
        self, table_name: str, df: pl.DataFrame
    ):
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
        logger.info(
            f"Table '{table_name}' created or already exists."
        )

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
