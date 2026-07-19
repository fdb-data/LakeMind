from __future__ import annotations
import os
import json
import psycopg2
from psycopg2 import pool
from psycopg2.extras import Json
from typing import Any


_pool: pool.ThreadedConnectionPool | None = None


def init_pool(host: str | None = None, port: int = 5432, db: str = "lakemind",
              user: str = "lakemind", password: str = "lakemind_pass",
              min_conn: int = 2, max_conn: int = 20) -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is not None:
        _pool.closeall()
    host = host or os.environ.get("PG_HOST", "localhost")
    port = int(os.environ.get("PG_PORT", port))
    db = os.environ.get("PG_DB", db)
    user = os.environ.get("PG_USER", user)
    password = os.environ.get("PG_PASSWORD", password)
    _pool = pool.ThreadedConnectionPool(min_conn, max_conn, host=host, port=port, dbname=db, user=user, password=password)
    return _pool


def get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        init_pool()
    return _pool


def get_conn():
    return get_pool().getconn()


def put_conn(conn):
    get_pool().putconn(conn)


def _adapt_params(params):
    if params is None:
        return None
    return tuple(Json(v) if isinstance(v, (dict, list)) else v for v in params)


def execute(query: str, params: tuple | None = None) -> Any:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, _adapt_params(params))
            if cur.description:
                rows = cur.fetchall()
                colnames = [desc[0] for desc in cur.description]
                result = [dict(zip(colnames, row)) for row in rows]
                conn.commit()
                return result
            conn.commit()
            return None
    except Exception:
        conn.rollback()
        raise
    finally:
        put_conn(conn)


def execute_one(query: str, params: tuple | None = None) -> dict | None:
    rows = execute(query, params)
    return rows[0] if rows else None


def get_database_url() -> str:
    host = os.environ.get("PG_HOST", "localhost")
    port = os.environ.get("PG_PORT", "5432")
    db = os.environ.get("PG_DB", "lakemind")
    user = os.environ.get("PG_USER", "lakemind")
    password = os.environ.get("PG_PASSWORD", "lakemind_pass")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
