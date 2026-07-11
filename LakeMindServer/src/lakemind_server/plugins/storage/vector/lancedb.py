from __future__ import annotations
from typing import Any
import pyarrow as pa
import lancedb


class LanceVectorStorage:
    def __init__(self, uri: str, **kwargs):
        self._uri = uri
        self._conns: dict[str, Any] = {}

    def _conn(self, db: str):
        if db not in self._conns:
            self._conns[db] = lancedb.connect(f"{self._uri}/{db}")
        return self._conns[db]

    def create_table(self, db: str, name: str, data: pa.Table, mode: str = "overwrite") -> None:
        self._conn(db).create_table(name, data=data, mode=mode)

    def table_exists(self, db: str, name: str) -> bool:
        return name in self.list_tables(db)

    def list_tables(self, db: str) -> list[str]:
        try:
            return self._conn(db).table_names()
        except Exception:
            return []

    def add(self, db: str, name: str, data: pa.Table) -> int:
        tbl = self._conn(db).open_table(name)
        tbl.add(data)
        return data.num_rows

    def search(self, db: str, name: str, query_vec: list[float],
               top_k: int = 5, filter: str | None = None) -> list[dict]:
        tbl = self._conn(db).open_table(name)
        q = tbl.search(query_vec).limit(top_k)
        if filter:
            q = q.where(filter)
        return q.to_list()

    def count_rows(self, db: str, name: str) -> int:
        try:
            return self._conn(db).open_table(name).count_rows()
        except Exception:
            return 0

    def describe(self, db: str, name: str) -> dict:
        tbl = self._conn(db).open_table(name)
        row_count = tbl.count_rows()
        return {
            "name": name,
            "row_count": row_count,
            "concept_count": row_count,
            "schema": tbl.schema.names,
        }

    def scan(self, db: str, name: str, limit: int = 100, offset: int = 0) -> list[dict]:
        tbl = self._conn(db).open_table(name)
        arrow_tbl = tbl.to_arrow()
        total = arrow_tbl.num_rows
        start = min(offset, total)
        end = min(offset + limit, total)
        sliced = arrow_tbl.slice(start, end - start)
        return sliced.to_pylist()

    def health(self) -> bool:
        try:
            lancedb.connect(self._uri)
            return True
        except Exception:
            return False
