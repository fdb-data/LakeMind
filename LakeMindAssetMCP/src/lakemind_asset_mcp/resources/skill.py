"""Skill 资产资源：lake://skills、lake://skills/{id}。"""
from __future__ import annotations

from ..context import get_tenant
from ..engines import Engines

DOMAIN = "skills"
META_TABLE = "skill_meta"


def register(mcp, engines: Engines) -> None:
    @mcp.resource("lake://skills")
    def list_skills() -> list[dict]:
        """可用 Skill 摘要列表。"""
        ctx = get_tenant()
        try:
            arrow = engines.iceberg.scan(ctx, DOMAIN, META_TABLE)
            return arrow.to_pylist()
        except Exception:
            return []

    @mcp.resource("lake://skills/{id}")
    def describe_skill(id: str) -> dict:
        """Skill 完整元信息 + 文件内容。"""
        ctx = get_tenant()
        arrow = engines.iceberg.scan(ctx, DOMAIN, META_TABLE)
        df = arrow.to_pylist()
        meta = next((r for r in df if r.get("skill_id") == id or r.get("name") == id), None)
        if meta is None:
            return {"error": "skill not found", "id": id}
        code = ""
        s3_uri = meta.get("s3_uri", "")
        if s3_uri.startswith("s3://"):
            rest = s3_uri[len("s3://") :]
            bucket, _, key = rest.partition("/")
            try:
                code = engines.s3.get(bucket, key).decode("utf-8")
            except Exception as e:
                code = f"<failed to load: {e}>"
        return {"meta": meta, "code": code}
