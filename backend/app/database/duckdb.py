from pathlib import Path
import duckdb
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_DIR = "duck_db"
DB_FILE = "data.db"
LEP_TRAITS_DOWNLOAD = "https://raw.githubusercontent.com/hhandika/LepTraits/refs/heads/main/consensus/consensus.csv"
LEP_TRAITS_PATH = "lep_traits_consensus.csv"
LEP_TRAITS_CONSENSUS = Path(DB_DIR).joinpath(LEP_TRAITS_PATH)


def get_duckdb_connection():
    """
    Get duckdb persistent connection.
    """
    dir_path: Path = Path(DB_DIR)

    if not dir_path.exists():
        dir_path.mkdir(parents=True)
    db_path = dir_path.joinpath(DB_FILE)
    return duckdb.connect(database=db_path)


def get_duckdb_client():
    """
    Get duckdb persistent client.
    """
    try:
        conn = get_duckdb_connection()
        return conn
    except Exception as e:
        logger.error(f"Error getting DuckDB client: {e}")
        return None


def init_duckdb():
    """
    Initialize DuckDB database and create necessary tables.
    """
    logger.info("Downloading LepTraits consensus data...")
    logger.info("Initializing DuckDB database...")
    conn = get_duckdb_client()
    if not conn:
        logger.error("Failed to initialize DuckDB client.")
        return

    try:
        conn.execute(
            f"CREATE OR REPLACE TABLE lep_traits_consensus AS SELECT * FROM '{LEP_TRAITS_DOWNLOAD}';"
        )
        logger.info("LepTraits consensus table created successfully.")

        tables = conn.execute("SHOW TABLES").fetchall()
        logger.info(f"Tables in DuckDB: {tables}")
        if not tables:
            logger.warning("No tables found in DuckDB database.")
        else:
            logger.info("DuckDB database initialized successfully.")
        # Show all header of lep_traits_consensus table
        headers = conn.execute(
            "PRAGMA table_info(lep_traits_consensus)"
        ).fetchall()
        logger.info(f"LepTraits consensus table headers:\n{headers}")
        df = conn.execute(
            "SELECT * FROM lep_traits_consensus LIMIT 5"
        ).pl()
        logger.info(f"LepTraits consensus table preview:\n{df}")
    except Exception as e:
        logger.error(f"Error initializing DuckDB: {e}")
    finally:
        conn.close()
