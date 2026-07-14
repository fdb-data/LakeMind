from __future__ import annotations
from datetime import datetime, timezone
import ulid
from ..db import execute, execute_one
from .audit_service import AuditService


def _ulid(prefix: str) -> str:
    return f"{prefix}_{str(ulid.new())}"


VALID_TRANSITIONS = {
    "PENDING": {"RUNNING", "APPROVAL_REQUIRED", "CANCELLED"},
    "APPROVAL_REQUIRED": {"APPROVED", "CANCELLED"},
    "APPROVED": {"RUNNING", "CANCELLED"},
    "RUNNING": {"SUCCEEDED", "FAILED", "CANCELLED"},
    "SUCCEEDED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}


class OperationService:

    @staticmethod
    def create(op_type: str, target_resource: str, initiator_id: str,
               initiator_channel: str, reason: str | None = None,
               risk_level: str = "LOW") -> dict:
        operation_id = _ulid("op")
        requires_approval = risk_level == "HIGH"
        status = "APPROVAL_REQUIRED" if requires_approval else "PENDING"
        execute(
            "INSERT INTO operations (operation_id, op_type, target_resource, initiator_id, initiator_channel, "
            "reason, risk_level, requires_approval, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (operation_id, op_type, target_resource, initiator_id, initiator_channel,
             reason, risk_level, requires_approval, status),
        )
        AuditService.record(
            event_type="operation.created",
            principal_id=initiator_id,
            resource_id=operation_id,
            action="create_operation",
            result="success",
            details={"op_type": op_type, "risk_level": risk_level},
        )
        return {"operation_id": operation_id, "status": status, "requires_approval": requires_approval}

    @staticmethod
    def approve(operation_id: str, approver_id: str) -> dict:
        row = execute_one("SELECT status FROM operations WHERE operation_id = %s", (operation_id,))
        if row is None:
            raise ValueError(f"Operation not found: {operation_id}")
        if row["status"] != "APPROVAL_REQUIRED":
            raise ValueError(f"Cannot approve operation in status: {row['status']}")
        execute(
            "UPDATE operations SET status = 'APPROVED', approver_id = %s, updated_at = %s WHERE operation_id = %s",
            (approver_id, datetime.now(timezone.utc), operation_id),
        )
        AuditService.record(
            event_type="operation.approved",
            principal_id=approver_id,
            resource_id=operation_id,
            action="approve_operation",
            result="success",
        )
        return {"operation_id": operation_id, "status": "APPROVED"}

    @staticmethod
    def execute(operation_id: str) -> dict:
        row = execute_one("SELECT status, requires_approval FROM operations WHERE operation_id = %s", (operation_id,))
        if row is None:
            raise ValueError(f"Operation not found: {operation_id}")
        if row["requires_approval"] and row["status"] != "APPROVED":
            raise ValueError("Operation not approved")
        if row["status"] not in ("PENDING", "APPROVED"):
            raise ValueError(f"Cannot execute operation in status: {row['status']}")
        execute(
            "UPDATE operations SET status = 'RUNNING', updated_at = %s WHERE operation_id = %s",
            (datetime.now(timezone.utc), operation_id),
        )
        return {"operation_id": operation_id, "status": "RUNNING"}

    @staticmethod
    def complete(operation_id: str, result: dict | None = None, failure_reason: str | None = None) -> dict:
        status = "FAILED" if failure_reason else "SUCCEEDED"
        execute(
            "UPDATE operations SET status = %s, result = %s, failure_reason = %s, updated_at = %s WHERE operation_id = %s",
            (status, result, failure_reason, datetime.now(timezone.utc), operation_id),
        )
        AuditService.record(
            event_type=f"operation.{status.lower()}",
            resource_id=operation_id,
            action="complete_operation",
            result=status.lower(),
        )
        return {"operation_id": operation_id, "status": status}

    @staticmethod
    def cancel(operation_id: str) -> dict:
        execute(
            "UPDATE operations SET status = 'CANCELLED', updated_at = %s WHERE operation_id = %s",
            (datetime.now(timezone.utc), operation_id),
        )
        return {"operation_id": operation_id, "status": "CANCELLED"}

    @staticmethod
    def get(operation_id: str) -> dict | None:
        return execute_one("SELECT * FROM operations WHERE operation_id = %s", (operation_id,))

    @staticmethod
    def list(status: str | None = None, op_type: str | None = None,
             page: int = 1, page_size: int = 50) -> dict:
        query = "SELECT * FROM operations WHERE 1=1"
        params: list = []
        if status:
            query += " AND status = %s"; params.append(status)
        if op_type:
            query += " AND op_type = %s"; params.append(op_type)
        query += " ORDER BY created_at DESC"
        items = execute(query, tuple(params) if params else None)
        total = len(items)
        offset = (page - 1) * page_size
        return {"items": items[offset:offset + page_size], "total": total, "page": page, "page_size": page_size}
