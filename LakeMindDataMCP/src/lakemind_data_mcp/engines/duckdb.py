"""DuckDB 即席分析辅助。"""
from __future__ import annotations

import pyarrow as pa

__all__ = ["query_arrow"]


def query_arrow(
    tables: dict[str, pa.Table],
    sql: str,
    params: list | None = None,
) -> list[dict]:
    """在内存中注册若干 Arrow 表后执行 SQL，返回 list[dict]。

    ``tables``: {duckdb_view_name: arrow_table}。
    """
    import duckdb

    con = duckdb.connect()
    try:
        for name, tbl in tables.items():
            con.register(name, tbl)
        cur = con.execute(sql, params or [])
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]
    finally:
        con.close()
