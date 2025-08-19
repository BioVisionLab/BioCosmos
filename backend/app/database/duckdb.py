from pathlib import Path
import duckdb
import logging
import polars as pl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_DIR = "duck_db"
DB_FILE = "data.db"


class DuckDBClient:
    """
    A simple DuckDB client wrapper.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = Path(DB_DIR)
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / DB_FILE
        self.conn = duckdb.connect(database=str(db_path))

    def execute(self, query: str):
        """Execute a SQL query and return the result.
        Args:
            query (str): The SQL query to execute.
        Returns:
            duckdb.DuckDBPyRelation: The result of the query.
        """
        return self.conn.execute(query)

    def execute_prepared(self, query: str, params: list):
        """Execute a prepared SQL query with parameters.
        Args:
            query (str): The SQL query to execute.
            params (list): The list of parameters to bind to the query.
        Returns:
            duckdb.DuckDBPyRelation: The result of the query.
        """
        return self.conn.execute(query, params)

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
