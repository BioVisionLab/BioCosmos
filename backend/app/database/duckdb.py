from pydantic import BaseModel, ConfigDict
from ..configs.config import get_duck_db_path
import duckdb
import logging
import polars as pl
from pydantic.alias_generators import to_camel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FtsSearchData(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    species: str
    matched_fields: list[str]
    score: float


class DuckDBClient:
    """
    A simple DuckDB client wrapper.
    """

    def __init__(self):
        db_path = get_duck_db_path()
        self.conn = duckdb.connect(database=str(db_path))
        # Init fts
        self.conn.sql("INSTALL fts;")
        self.conn.sql("LOAD fts;")
        logger.info(f"DuckDB connected at {db_path}")

    def index_table(
        self,
        table_name: str,
        id_column: str,
        columns: list[str],
        overwrite: bool = False,
    ):
        """Create a full-text search index on the specified columns of a table.
        Args:
            table_name (str): The name of the table to index.
            id_column (str): The unique document identifier column (e.g., primary key).
            columns (list[str]): The list of column names to include in the index.
            overwrite (bool): Whether to overwrite an existing index. Defaults to False.
        """
        # Each column must be a separate quoted argument ? NOT a joined string
        columns_args = ", ".join(f"'{col}'" for col in columns)
        self.conn.execute(
            f"PRAGMA create_fts_index('{table_name}', '{id_column}', {columns_args}, overwrite = {int(overwrite)})"
        )
        logger.info(
            f"Full-text search index created on '{table_name}' (id='{id_column}') "
            f"for columns: {', '.join(columns)}"
        )

    def search_fts(
        self,
        table_name: str,
        id_column: str,
        query: str,
        fields: list[str] | None = None,
        limit: int = 100,
        unique_species: bool = False,
    ) -> list[FtsSearchData]:
        """Perform a full-text search on the specified table using DuckDB's FTS extension."""

        search_fields = fields or []
        query_esc = query.replace("'", "''")

        macro = f"fts_main_{table_name}.match_bm25"
        fields_joined = ", ".join(search_fields)
        fields_arg = f", fields := '{fields_joined}'" if search_fields else ""

        quoted_id = f'"{id_column}"'
        quoted_species = '"species"'

        if search_fields:
            field_cols = ", ".join(
                f'CAST("{f}" AS VARCHAR) AS "{f}"' for f in search_fields
            )
            select_cols = f"{quoted_species}, {field_cols}, "
        else:
            select_cols = f"{quoted_species}, "

        # Push Down Optimization: Deduplicate, sort, and limit entirely in DuckDB
        if unique_species:
            # Uses a window function to find the top score per species
            sql = f"""
                    WITH matches AS (
                        SELECT {select_cols}
                            {macro}({quoted_id}, '{query_esc}'{fields_arg}) AS score
                        FROM "{table_name}"
                    )
                    SELECT * EXCLUDE (rn)
                    FROM (
                        SELECT *, ROW_NUMBER() OVER (PARTITION BY "species" ORDER BY score DESC) as rn
                        FROM matches
                        WHERE score IS NOT NULL
                    )
                    WHERE rn = 1
                    ORDER BY score DESC
                    LIMIT {limit}
                """
        else:
            sql = f"""
                    SELECT {select_cols}
                        {macro}({quoted_id}, '{query_esc}'{fields_arg}) AS score
                    FROM "{table_name}"
                    WHERE score IS NOT NULL
                    ORDER BY score DESC
                    LIMIT {limit}
                """

        df = self.conn.sql(sql).pl()

        # Tokenize the *original* query (not the escaped one) to mimic BM25 token matching
        query_tokens = [t.lower() for t in query.split()]

        results = []
        for row in df.iter_rows(named=True):
            if not row["species"] or not str(row["species"]).strip():
                continue

            matched = []
            if search_fields:
                for f in search_fields:
                    if f in row and row[f]:
                        field_val = str(row[f]).lower()
                        # Check against individual tokens instead of exact full-string match
                        if any(token in field_val for token in query_tokens):
                            matched.append(f)

            results.append(
                FtsSearchData(
                    species=str(row["species"]).strip().lower().replace(" ", "_"),
                    score=row["score"],
                    matched_fields=matched,
                )
            )

        return results

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

    def execute_prepared_to_pl(self, query: str, params: list) -> pl.DataFrame:
        """Execute a prepared SQL query with parameters and return the result as a Polars DataFrame.
        Args:
            query (str): The SQL query to execute.
            params (list): The list of parameters to bind to the query.
        Returns:
            pl.DataFrame: The result of the query as a Polars DataFrame.
        """
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
