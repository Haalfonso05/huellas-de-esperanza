"""Pool de conexiones a PostgreSQL (Supabase)."""
import os

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

pool = ConnectionPool(
    DATABASE_URL,
    min_size=1,
    max_size=3,
    open=False,
    kwargs={"row_factory": dict_row},
    check=ConnectionPool.check_connection,
)
