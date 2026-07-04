"""Skill 资产工具：search_skill。"""
from __future__ import annotations

from typing import Any

from ..context import get_tenant
from ..engines import Engines
from ._helpers import audited, require_scope

SCOPE = "data"
SKILL_VEC_TABLE = "skill_vectors"   # Lance 向量索引表名


def register(mcp, engines: Engines, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def search_skill(query: str, top_k: int = 5) -> dict[str, Any]:
        """语义搜索匹配的 Skill。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        if not engines.lancedb.table_exists(ctx, SKILL_VEC_TABLE):
            return {"query": query, "skills": [], "count": 0}
        qvec = engines.embedding.embed([query])[0]
        hits = engines.lancedb.search(ctx, SKILL_VEC_TABLE, qvec, top_k)
        skills = [
            {
                "skill_id": h.get("skill_id"),
                "name": h.get("name"),
                "description": h.get("description"),
                "_distance": h.get("_distance"),
            }
            for h in hits
        ]
        return {"query": query, "skills": skills, "count": len(skills)}
