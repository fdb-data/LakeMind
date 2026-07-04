from __future__ import annotations
import duckdb
import pyarrow as pa


class DuckDBSQLCompute:
    def __init__(self, memory_limit: str = "2GB", **kwargs):
        self._memory_limit = memory_limit

    def execute(self, sql: str, tables: dict[str, pa.Table] | None = None) -> list[dict]:
        con = duckdb.connect()
        try:
            con.execute(f"SET memory_limit='{self._memory_limit}'")
            if tables:
                for name, tbl in tables.items():
                    con.register(name, tbl)
            cur = con.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]
        finally:
            con.close()

    def health(self) -> bool:
        try:
            con = duckdb.connect()
            con.close()
            return True
        except Exception:
            return False
