"""Experience 资产资源：lake://experience、lake://experience/{id}。"""
from __future__ import annotations

from ..context import get_tenant
from ..engines import Engines

DOMAIN = "experience"
META_TABLE = "exp_record"


def register(mcp, engines: Engines) -> None:
    @mcp.resource("lake://experience")
    def list_experience() -> list[dict]:
        """经验记录摘要列表。"""
        ctx = get_tenant()
        try:
            return engines.iceberg.scan(ctx, DOMAIN, META_TABLE).to_pylist()
        except Exception:
            return []

    @mcp.resource("lake://experience/{id}")
    def describe_experience(id: str) -> dict:
        """某条经验详情。"""
        ctx = get_tenant()
        try:
            rows = engines.iceberg.scan(ctx, DOMAIN, META_TABLE).to_pylist()
            return next((r for r in rows if r.get("exp_id") == id), {"error": "not found"})
        except Exception:
            return {"error": "not found"}
