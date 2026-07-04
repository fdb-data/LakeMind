"""Data 资产资源：lake://data、lake://data/{name}。"""
from __future__ import annotations

from ..context import get_tenant
from ..engines import Engines

DOMAIN = "data"


def register(mcp, engines: Engines) -> None:
    @mcp.resource("lake://data")
    def list_datasets() -> list[dict]:
        """数据集列表。"""
        ctx = get_tenant()
        tables = engines.iceberg.list_tables(ctx, DOMAIN)
        out = []
        for t in tables:
            try:
                out.append(engines.iceberg.describe(ctx, DOMAIN, t))
            except Exception:
                out.append({"name": t})
        return out

    @mcp.resource("lake://data/{name}")
    def describe_dataset(name: str) -> dict:
        """表结构、分区、行数。"""
        ctx = get_tenant()
        return engines.iceberg.describe(ctx, DOMAIN, name)
