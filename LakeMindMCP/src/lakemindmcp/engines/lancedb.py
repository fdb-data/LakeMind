"""LanceDB 客户端（向量检索，按租户分库）。"""
from __future__ import annotations

from typing import Any

import pyarrow as pa

from ..config import LanceCfg
from ..context import TenantContext

__all__ = ["LanceDBClient"]


class LanceDBClient:
    def __init__(self, cfg: LanceCfg) -> None:
        self._cfg = cfg
        self._db = None

    def _ensure(self):
        if self._db is None:
            import lancedb

            self._db = lancedb.connect(self._cfg.uri)
        return self._db

    def _tenant_db(self, ctx: TenantContext):
        """每租户独立数据库（目录）。"""
        import lancedb

        return lancedb.connect(f"{self._cfg.uri}/{ctx.lancedb_name()}")

    def list_tables(self, ctx: TenantContext) -> list[str]:
        try:
            return self._tenant_db(ctx).table_names()
        except Exception:
            return []

    def table_exists(self, ctx: TenantContext, name: str) -> bool:
        return name in self.list_tables(ctx)

    def create_table(self, ctx: TenantContext, name: str, data: pa.Table, mode: str = "overwrite"):
        return self._tenant_db(ctx).create_table(name, data=data, mode=mode)

    def add(self, ctx: TenantContext, name: str, data: pa.Table):
        tbl = self._tenant_db(ctx).open_table(name)
        tbl.add(data)
        return data.num_rows

    def count_rows(self, ctx: TenantContext, name: str) -> int:
        try:
            return self._tenant_db(ctx).open_table(name).count_rows()
        except Exception:
            return 0

    def search(
        self,
        ctx: TenantContext,
        name: str,
        query_vec: list[float],
        top_k: int = 5,
        filter: str | None = None,
    ) -> list[dict[str, Any]]:
        tbl = self._tenant_db(ctx).open_table(name)
        q = tbl.search(query_vec).limit(top_k)
        if filter:
            q = q.where(filter)
        return q.to_list()

    def describe(self, ctx: TenantContext, name: str) -> dict[str, Any]:
        tbl = self._tenant_db(ctx).open_table(name)
        return {"name": name, "row_count": tbl.count_rows(), "schema": tbl.schema.names}
