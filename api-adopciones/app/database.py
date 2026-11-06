"""Conexión a PostgreSQL (Supabase) mediante un pool de conexiones."""
import os

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

pool = ConnectionPool(
    DATABASE_URL,
    min_size=1,
    max_size=3,  # El plan gratuito de Supabase admite pocas conexiones.
    open=False,
    kwargs={"row_factory": dict_row},
    # Descarta conexiones que la nube haya cerrado por inactividad.
    check=ConnectionPool.check_connection,
)
