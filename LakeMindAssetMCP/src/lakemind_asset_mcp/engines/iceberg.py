"""PyIceberg catalog 客户端（直连 S3，SQL catalog）。

按租户隔离 namespace：``{tenant_id}_{domain}``。
表 location 自动加租户前缀：``s3://{bucket}/warehouse/{tenant_id}/{domain}/{table}``。
"""
from __future__ import annotations

from typing import Any

import pyarrow as pa

from ..config import IcebergCfg, S3Cfg
from ..context import TenantContext

__all__ = ["IcebergClient"]


class IcebergClient:
    def __init__(self, iceberg_cfg: IcebergCfg, s3_cfg: S3Cfg) -> None:
        self._iceberg = iceberg_cfg
        self._s3 = s3_cfg
        self._catalog = None
        # warehouse 形如 s3://lakemind-iceberg/warehouse
        wh = iceberg_cfg.warehouse
        self._bucket = wh.split("//")[1].split("/")[0]
        self._wh_path = wh[len(f"s3://{self._bucket}") :].lstrip("/")

    def _ensure(self):
        if self._catalog is None:
            from pyiceberg.catalog import load_catalog

            self._catalog = load_catalog(
                self._iceberg.catalog_name,
                **{
                    "type": "sql",
                    "uri": self._iceberg.sql_uri,
                    "warehouse": self._iceberg.warehouse,
                    "s3.endpoint": self._s3.endpoint,
                    "s3.access-key-id": self._s3.access_key,
                    "s3.secret-access-key": self._s3.secret_key,
                    "s3.region": self._s3.region,
                },
            )
        return self._catalog

    # ── 命名 ──────────────────────────────────────────────
    def namespace(self, ctx: TenantContext, domain: str) -> str:
        return ctx.iceberg_namespace(domain)

    def table_ref(self, ctx: TenantContext, domain: str, table: str) -> str:
        return f"{self.namespace(ctx, domain)}.{table}"

    def table_location(self, ctx: TenantContext, domain: str, table: str) -> str:
        return f"s3://{self._bucket}/{self._wh_path}/{ctx.tenant_id}/{domain}/{table}"

    # ── namespace ────────────────────────────────────────
    def ensure_namespace(self, ctx: TenantContext, domain: str) -> str:
        ns = self.namespace(ctx, domain)
        cat = self._ensure()
        try:
            cat.create_namespace(ns)
        except Exception:
            pass
        return ns

    # ── 表操作 ───────────────────────────────────────────
    def list_tables(self, ctx: TenantContext, domain: str) -> list[str]:
        ns = self.namespace(ctx, domain)
        cat = self._ensure()
        try:
            out = []
            for t in cat.list_tables(ns):
                if isinstance(t, tuple):
                    out.append(t[-1])
                else:
                    out.append(str(t).split(".")[-1])
            return out
        except Exception:
            return []

    def table_exists(self, ctx: TenantContext, domain: str, table: str) -> bool:
        cat = self._ensure()
        try:
            cat.load_table(self.table_ref(ctx, domain, table))
            return True
        except Exception:
            return False

    def create_table_from_arrow(
        self, ctx: TenantContext, domain: str, table: str, arrow_schema: pa.Schema
    ):
        self.ensure_namespace(ctx, domain)
        from .schema_convert import arrow_to_iceberg_schema

        iceberg_schema = arrow_to_iceberg_schema(arrow_schema)
        cat = self._ensure()
        return cat.create_table(
            self.table_ref(ctx, domain, table),
            schema=iceberg_schema,
            location=self.table_location(ctx, domain, table),
        )

    def load_table(self, ctx: TenantContext, domain: str, table: str):
        return self._ensure().load_table(self.table_ref(ctx, domain, table))

    def append(self, ctx: TenantContext, domain: str, table: str, data: pa.Table) -> int:
        t = self.load_table(ctx, domain, table)
        t.append(data)
        return data.num_rows

    def overwrite(self, ctx: TenantContext, domain: str, table: str, data: pa.Table) -> int:
        t = self.load_table(ctx, domain, table)
        t.overwrite(data)
        return data.num_rows

    def scan(self, ctx: TenantContext, domain: str, table: str) -> pa.Table:
        return self.load_table(ctx, domain, table).scan().to_arrow()

    def describe(self, ctx: TenantContext, domain: str, table: str) -> dict[str, Any]:
        t = self.load_table(ctx, domain, table)
        arrow = t.scan().to_arrow()
        return {
            "name": table,
            "schema": {f.name: str(f.type) for f in arrow.schema},
            "columns": list(arrow.schema.names),
            "row_count": arrow.num_rows,
            "location": t.metadata_location,
        }
