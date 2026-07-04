"""Data 资产工具：query_table / write_table / execute_sql。"""
from __future__ import annotations

from typing import Any

import pyarrow as pa

from ..context import get_tenant
from ..engines import Engines
from ..engines.duckdb import query_arrow
from ._helpers import audited, require_scope

DOMAIN = "data"
SCOPE = "data"


def register(mcp, engines: Engines, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def query_table(
        table: str,
        columns: list[str] | None = None,
        filter: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """查询结构化数据表（推荐优先使用）。filter 为 SQL WHERE 表达式。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        arrow = engines.iceberg.scan(ctx, DOMAIN, table)
        cols_sql = ", ".join(columns) if columns else "*"
        where = f"WHERE {filter}" if filter else ""
        rows = query_arrow({"t": arrow}, f"SELECT {cols_sql} FROM t {where} LIMIT {limit}")
        return {"rows": rows, "count": len(rows)}

    @mcp.tool()
    @audited(redact_keys)
    async def write_table(
        table: str, rows: list[dict], mode: str = "append"
    ) -> dict[str, Any]:
        """写入数据。mode: append | overwrite。表不存在则自动创建。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        data = pa.Table.from_pylist(rows)
        if not engines.iceberg.table_exists(ctx, DOMAIN, table):
            engines.iceberg.create_table_from_arrow(ctx, DOMAIN, table, data.schema)
        n = (
            engines.iceberg.append(ctx, DOMAIN, table, data)
            if mode == "append"
            else engines.iceberg.overwrite(ctx, DOMAIN, table, data)
        )
        return {"table": table, "rows_written": n, "mode": mode}

    @mcp.tool()
    @audited(redact_keys)
    async def execute_sql(sql: str) -> dict[str, Any]:
        """高级模式：在当前租户的全部 data 表上执行任意 SQL。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        tables = engines.iceberg.list_tables(ctx, DOMAIN)
        views: dict[str, pa.Table] = {}
        for t in tables:
            try:
                views[t] = engines.iceberg.scan(ctx, DOMAIN, t)
            except Exception:
                pass
        rows = query_arrow(views, sql)
        return {"rows": rows, "count": len(rows)}
