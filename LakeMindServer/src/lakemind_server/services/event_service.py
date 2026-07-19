from __future__ import annotations
import json
import uuid
from datetime import datetime, timedelta, timezone
from ..db import execute, execute_one


_RETENTION_DAYS = 7


class EventService:

    @staticmethod
    def emit(event_type: str, scope_type: str = "TENANT", scope_id: str | None = None,
             resource_type: str | None = None, resource_id: str | None = None,
             payload: dict | None = None) -> str:
        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        retention_until = now + timedelta(days=_RETENTION_DAYS)
        execute(
            "INSERT INTO event_stream (event_id, event_type, scope_type, scope_id, "
            "resource_type, resource_id, payload, retention_until) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)",
            (event_id, event_type, scope_type, scope_id,
             resource_type, resource_id, json.dumps(payload or {}), retention_until),
        )
        return event_id

    @staticmethod
    def get_unpublished(limit: int = 100) -> list[dict]:
        return execute(
            "SELECT * FROM event_stream WHERE published_at IS NULL "
            "ORDER BY sequence ASC LIMIT %s",
            (limit,),
        )

    @staticmethod
    def mark_published(event_id: str) -> None:
        execute(
            "UPDATE event_stream SET published_at = %s WHERE event_id = %s",
            (datetime.now(timezone.utc), event_id),
        )

    @staticmethod
    def mark_failed(event_id: str, error: str) -> None:
        execute(
            "UPDATE event_stream SET publish_attempts = publish_attempts + 1, "
            "last_publish_error = %s WHERE event_id = %s",
            (error, event_id),
        )

    @staticmethod
    def query(after_sequence: int = 0, event_type: str | None = None,
              resource_type: str | None = None, scope_type: str | None = None,
              scope_id: str | None = None, page_size: int = 100) -> dict:
        conditions = ["sequence > %s"]
        params: list = [after_sequence]
        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type)
        if resource_type:
            conditions.append("resource_type = %s")
            params.append(resource_type)
        if scope_type:
            conditions.append("scope_type = %s")
            params.append(scope_type)
        if scope_id:
            conditions.append("scope_id = %s")
            params.append(scope_id)
        where = " AND ".join(conditions)
        items = execute(
            f"SELECT * FROM event_stream WHERE {where} ORDER BY sequence ASC LIMIT %s",
            tuple(params + [page_size + 1]),
        )
        has_more = len(items) > page_size
        items = items[:page_size]
        last_seq = items[-1]["sequence"] if items else after_sequence
        return {"items": items, "has_more": has_more, "last_sequence": last_seq}

    @staticmethod
    def cleanup_expired() -> int:
        now = datetime.now(timezone.utc)
        result = execute_one(
            "WITH deleted AS (DELETE FROM event_stream "
            "WHERE retention_until < %s AND published_at IS NOT NULL "
            "RETURNING 1) SELECT count(*) AS cnt FROM deleted",
            (now,),
        )
        return result["cnt"] if result else 0

    @staticmethod
    def get_backlog_count() -> int:
        row = execute_one("SELECT count(*) AS cnt FROM event_stream WHERE published_at IS NULL")
        return row["cnt"] if row else 0
