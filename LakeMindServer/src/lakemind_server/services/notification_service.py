from __future__ import annotations
import ulid
from datetime import datetime, timezone
from ..db import execute, execute_one


class NotificationService:

    @staticmethod
    def _ulid() -> str:
        return f"ntf_{str(ulid.new())}"

    @staticmethod
    def create(principal_id: str | None, category: str, title: str,
               scope_type: str = "TENANT", scope_id: str | None = None,
               severity: str = "info", message: str | None = None,
               resource_type: str | None = None, resource_id: str | None = None) -> str:
        notification_id = NotificationService._ulid()
        execute(
            "INSERT INTO notifications (notification_id, principal_id, scope_type, scope_id, "
            "category, severity, title, message, resource_type, resource_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (notification_id, principal_id, scope_type, scope_id,
             category, severity, title, message, resource_type, resource_id),
        )
        from .event_service import EventService
        EventService.emit(
            event_type="notification.created",
            scope_type=scope_type,
            scope_id=scope_id,
            resource_type="notification",
            resource_id=notification_id,
            payload={"notification_id": notification_id, "category": category, "severity": severity},
        )
        return notification_id

    @staticmethod
    def list_for_principal(principal_id: str, unread_only: bool = False,
                           page: int = 1, page_size: int = 20) -> dict:
        conditions = ["principal_id = %s"]
        params: list = [principal_id]
        if unread_only:
            conditions.append("read = false")
        where = " AND ".join(conditions)
        offset = (page - 1) * page_size
        items = execute(
            f"SELECT * FROM notifications WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )
        total_row = execute_one(
            f"SELECT count(*) AS cnt FROM notifications WHERE {where}",
            tuple(params),
        )
        return {
            "items": items,
            "total": total_row["cnt"] if total_row else 0,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def unread_count(principal_id: str) -> int:
        row = execute_one(
            "SELECT count(*) AS cnt FROM notifications WHERE principal_id = %s AND read = false",
            (principal_id,),
        )
        return row["cnt"] if row else 0

    @staticmethod
    def mark_read(notification_id: str, principal_id: str) -> None:
        execute(
            "UPDATE notifications SET read = true, read_at = %s "
            "WHERE notification_id = %s AND principal_id = %s",
            (datetime.now(timezone.utc), notification_id, principal_id),
        )
