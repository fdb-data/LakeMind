from __future__ import annotations
from datetime import datetime, timezone
import json
import ulid
from ..db import execute, execute_one


def _ulid(prefix: str) -> str:
    return f"{prefix}_{str(ulid.new())}"


class AuditService:

    @staticmethod
    def record(event_type: str, principal_id: str | None = None,
               tenant_id: str | None = None, resource_id: str | None = None,
               action: str = "", result: str = "success",
               details: dict | None = None, request_id: str | None = None) -> dict:
        audit_id = _ulid("aud")
        execute(
            "INSERT INTO audit_log (audit_id, event_type, principal_id, tenant_id, resource_id, action, result, details, request_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (audit_id, event_type, principal_id, tenant_id, resource_id, action, result, json.dumps(details or {}), request_id),
        )
        return {"audit_id": audit_id, "event_type": event_type, "result": result}

    @staticmethod
    def query(event_type: str | None = None, principal_id: str | None = None,
              tenant_id: str | None = None, resource_id: str | None = None,
              start_time: datetime | None = None, end_time: datetime | None = None,
              page: int = 1, page_size: int = 50) -> dict:
        query_str = "SELECT * FROM audit_log WHERE 1=1"
        params: list = []
        if event_type:
            query_str += " AND event_type = %s"; params.append(event_type)
        if principal_id:
            query_str += " AND principal_id = %s"; params.append(principal_id)
        if tenant_id:
            query_str += " AND tenant_id = %s"; params.append(tenant_id)
        if resource_id:
            query_str += " AND resource_id = %s"; params.append(resource_id)
        if start_time:
            query_str += " AND created_at >= %s"; params.append(start_time)
        if end_time:
            query_str += " AND created_at <= %s"; params.append(end_time)

        count_str = f"SELECT COUNT(*) as total FROM ({query_str}) sub"
        count_row = execute_one(count_str, tuple(params) if params else None)
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        query_str += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([page_size, offset])
        items = execute(query_str, tuple(params))
        return {"items": items, "total": total, "page": page, "page_size": page_size, "has_next": offset + page_size < total}

    @staticmethod
    def export(event_type: str | None = None, tenant_id: str | None = None,
               start_time: datetime | None = None, end_time: datetime | None = None) -> list[dict]:
        query_str = "SELECT * FROM audit_log WHERE 1=1"
        params: list = []
        if event_type:
            query_str += " AND event_type = %s"; params.append(event_type)
        if tenant_id:
            query_str += " AND tenant_id = %s"; params.append(tenant_id)
        if start_time:
            query_str += " AND created_at >= %s"; params.append(start_time)
        if end_time:
            query_str += " AND created_at <= %s"; params.append(end_time)
        query_str += " ORDER BY created_at DESC"
        return execute(query_str, tuple(params) if params else None)
