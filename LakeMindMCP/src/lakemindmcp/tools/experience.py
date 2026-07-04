"""Experience 资产工具：record_experience。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pyarrow as pa

from ..context import get_tenant
from ..engines import Engines
from ._helpers import audited, require_scope

SCOPE = "data"
DOMAIN = "experience"
META_TABLE = "exp_record"
VALID_TYPES = ("success", "failure", "reflection")


def _ensure_table(engines: Engines, ctx) -> None:
    if not engines.iceberg.table_exists(ctx, DOMAIN, META_TABLE):
        schema = pa.schema(
            [
                pa.field("exp_id", pa.string()),
                pa.field("type", pa.string()),
                pa.field("content", pa.string()),
                pa.field("tags", pa.list_(pa.string())),
                pa.field("score", pa.float64()),
                pa.field("created_at", pa.string()),
            ]
        )
        engines.iceberg.create_table_from_arrow(ctx, DOMAIN, META_TABLE, schema)


def register(mcp, engines: Engines, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def record_experience(
        type: str, content: str, tags: list[str] | None = None, score: float | None = None
    ) -> dict[str, Any]:
        """记录成功/失败/反思经验。type ∈ success/failure/reflection。"""
        require_scope(SCOPE)
        if type not in VALID_TYPES:
            raise ValueError(f"invalid type: {type}; must be one of {VALID_TYPES}")
        ctx = get_tenant()
        _ensure_table(engines, ctx)
        exp_id = f"exp-{uuid.uuid4().hex[:12]}"
        row = pa.table(
            {
                "exp_id": [exp_id],
                "type": [type],
                "content": [content],
                "tags": pa.array([tags or []], type=pa.list_(pa.string())),
                "score": pa.array([score], type=pa.float64()) if score is not None else pa.array([None], type=pa.float64()),
                "created_at": [datetime.now(timezone.utc).isoformat()],
            }
        )
        engines.iceberg.append(ctx, DOMAIN, META_TABLE, row)
        return {"exp_id": exp_id, "type": type}
