import os
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Initialize a connection pool
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL lipsește. Configurează conexiunea la baza de date înainte de pornirea backend-ului."
    )

try:
    conn_pool = ConnectionPool(
        conninfo=DATABASE_URL,
        min_size=1,
        max_size=10,
        # Check connection health before giving it to the application
        check=ConnectionPool.check_connection,
        # Maximum time (seconds) a connection can stay idle in the pool
        max_idle=300,
        # Reconnect if the connection has been open too long (seconds)
        max_lifetime=600,
        # Number of reconnection attempts
        reconnect_timeout=60,
    )
except Exception as e:
    raise RuntimeError(f"Error initializing connection pool: {e}") from e


def get_db_conn():
    """Dependency that yields a connection from the pool and returns it."""
    if conn_pool is None:
        raise ConnectionError("Database connection pool is not initialized.")

    with conn_pool.connection() as conn:
        yield conn


def close_db_pool():
    """Closes the connection pool."""
    if conn_pool:
        conn_pool.close()