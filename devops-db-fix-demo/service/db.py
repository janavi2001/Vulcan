import os
import time
import psycopg2
from typing import Any, List, Tuple

# Return value type: psycopg2.extensions.connection
def get_connection():
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    name = os.getenv("DB_NAME", "demo")
    user = os.getenv("DB_USER", "demo")
    pwd  = os.getenv("DB_PASSWORD", "demo")
    timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "1"))

    last_err = None
    for _ in range(3):
        try:
            conn = psycopg2.connect(
                host=host, port=port, dbname=name, user=user, password=pwd,
                connect_timeout=timeout
            )
            return conn
        except Exception as e:
            last_err = e
            time.sleep(0.3)
    raise last_err

# Return value type: List[Tuple[Any, ...]]
def fetch_users():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM users ORDER BY id ASC")
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()
