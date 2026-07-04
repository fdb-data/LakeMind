"""Admin 工具域（仅 Steward，scope=admin）。

- register_knowledge(name, location, description?) — 注册知识库（建 Lance 空表 + S3 目录）
- create_dataset(name, schema, partition?) — 建数据集（Iceberg 空表）
- register_skill(name, location, metadata?) — 注册 Skill（S3 文件 + Iceberg 元信息 + Lance 向量索引）
- optimize_asset(asset_type, asset_name) — 预留：触发优化
- get_system_health() — 组件健康
"""
from __future__ import annotations

import uuid
from typing import Any

import pyarrow as pa

from ..context import get_tenant
from ..engines import Engines
from ..resources.knowledge import KB_PREFIX
from ._helpers import audited, require_scope

SCOPE = "admin"


def register(mcp, engines: Engines, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def register_knowledge(
        name: str, location: str, description: str | None = None
    ) -> dict[str, Any]:
        """注册知识库：在当前租户下创建空 Lance 向量表。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        dim = engines.embedding.dim
        table = f"{KB_PREFIX}{name}"
        empty = pa.table(
            {
                "doc_uri": pa.array([], pa.string()),
                "title": pa.array([], pa.string()),
                "content": pa.array([], pa.string()),
                "vector": pa.array([], pa.list_(pa.float32(), dim)),
            }
        )
        engines.lancedb.create_table(ctx, table, empty, mode="overwrite")
        return {"knowledge": name, "table": table, "location": location, "dim": dim}

    @mcp.tool()
    @audited(redact_keys)
    async def create_dataset(
        name: str, schema: dict[str, str], partition: str | None = None
    ) -> dict[str, Any]:
        """建数据集（Iceberg 空表）。schema 为 {列名: pyarrow 类型名}。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        fields = []
        type_map = {
            "string": pa.string(),
            "int64": pa.int64(),
            "int32": pa.int32(),
            "float64": pa.float64(),
            "float32": pa.float32(),
            "bool": pa.bool_(),
            "timestamp": pa.timestamp("us"),
        }
        for col, tname in schema.items():
            fields.append(pa.field(col, type_map.get(tname, pa.string())))
        engines.iceberg.create_table_from_arrow(ctx, "data", name, pa.schema(fields))
        return {"dataset": name, "columns": list(schema.keys())}

    @mcp.tool()
    @audited(redact_keys)
    async def register_skill(
        name: str, location: str, metadata: dict | None = None
    ) -> dict[str, Any]:
        """注册 Skill：上传代码到 S3、写 Iceberg 元信息、建 Lance 向量索引。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        meta = metadata or {}
        bucket = "lakemind-filesets"
        s3_key = f"{ctx.tenant_id}/skills/{name}.py"
        code = meta.get("code", "")
        engines.s3.put(bucket, s3_key, code)
        s3_uri = f"s3://{bucket}/{s3_key}"

        # Iceberg 元信息
        domain = "skills"
        meta_table = "skill_meta"
        if not engines.iceberg.table_exists(ctx, domain, meta_table):
            schema = pa.schema(
                [
                    pa.field("skill_id", pa.string()),
                    pa.field("name", pa.string()),
                    pa.field("description", pa.string()),
                    pa.field("version", pa.string()),
                    pa.field("owner", pa.string()),
                    pa.field("s3_uri", pa.string()),
                ]
            )
            engines.iceberg.create_table_from_arrow(ctx, domain, meta_table, schema)
        skill_id = f"skill-{uuid.uuid4().hex[:8]}"
        row = pa.table(
            {
                "skill_id": [skill_id],
                "name": [name],
                "description": [meta.get("description", "")],
                "version": [meta.get("version", "1.0.0")],
                "owner": [ctx.agent_id],
                "s3_uri": [s3_uri],
            }
        )
        engines.iceberg.append(ctx, domain, meta_table, row)

        # Lance 向量索引
        dim = engines.embedding.dim
        vec = engines.embedding.embed([meta.get("description", name)])[0]
        vec_table = "skill_vectors"
        vec_row = pa.table(
            {
                "skill_id": [skill_id],
                "name": [name],
                "description": [meta.get("description", "")],
                "vector": pa.array([vec], type=pa.list_(pa.float32(), dim)),
            }
        )
        if engines.lancedb.table_exists(ctx, vec_table):
            engines.lancedb.add(ctx, vec_table, vec_row)
        else:
            engines.lancedb.create_table(ctx, vec_table, vec_row, mode="create")
        return {"skill_id": skill_id, "name": name, "s3_uri": s3_uri}

    @mcp.tool()
    @audited(redact_keys)
    async def optimize_asset(asset_type: str, asset_name: str) -> dict[str, Any]:
        """触发资产优化（MVP 占位）。"""
        require_scope(SCOPE)
        return {"asset_type": asset_type, "asset_name": asset_name, "status": "no-op (MVP)"}

    @mcp.tool()
    @audited(redact_keys)
    async def get_system_health() -> dict[str, Any]:
        """组件健康检查。"""
        require_scope(SCOPE)
        from ..health import system_health

        return system_health(engines)
