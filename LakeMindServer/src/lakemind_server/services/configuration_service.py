from __future__ import annotations
from datetime import datetime, timezone
import ulid
from ..db import execute, execute_one
from .audit_service import AuditService


def _ulid(prefix: str) -> str:
    return f"{prefix}_{str(ulid.new())}"


CONFIG_SCHEMA = {
    "platform": {
        "job.default_timeout": {"type": "int", "default": 3600, "min": 60, "max": 86400, "immutable": False},
        "job.default_retries": {"type": "int", "default": 3, "min": 0, "max": 10, "immutable": False},
        "memory.default_retention_days": {"type": "int", "default": 90, "immutable": False},
        "asset.max_size_mb": {"type": "int", "default": 1024, "immutable": False},
        "steward.auto_governance_enabled": {"type": "bool", "default": False, "immutable": False},
        "steward.auto_action_level": {"type": "str", "default": "observe", "enum": ["observe", "low_risk"], "immutable": False},
    },
    "tenant": {
        "job.max_concurrent": {"type": "int", "default": 10, "min": 1, "max": 100, "immutable": False},
        "job.max_cpu": {"type": "float", "default": 4.0, "immutable": False},
        "job.max_memory_mb": {"type": "int", "default": 8192, "immutable": False},
        "memory.retention_days": {"type": "int", "default": 90, "immutable": False},
        "asset.capacity_mb": {"type": "int", "default": 10240, "immutable": False},
    },
}

IMMUTABLE_KEYS = {"tenant_id", "secret_permissions", "skill_trust_level", "network_egress"}


class ConfigurationService:

    @staticmethod
    def get(scope: str, key: str | None = None) -> dict | None:
        row = execute_one(
            "SELECT values FROM config_revisions WHERE scope = %s AND is_active = TRUE ORDER BY created_at DESC LIMIT 1",
            (scope,),
        )
        if row is None:
            return ConfigurationService._get_defaults(scope, key)
        values = row["values"]
        if key:
            return {"key": key, "value": values.get(key)}
        return {"scope": scope, "values": values}

    @staticmethod
    def set(scope: str, key: str, value, reason: str, created_by: str) -> dict:
        if key in IMMUTABLE_KEYS:
            raise ValueError(f"Cannot modify immutable key: {key}")
        current = ConfigurationService.get(scope)
        current_values = current.get("values", {}) if current else {}
        new_values = dict(current_values)
        new_values[key] = value

        revision_id = _ulid("cfgr")
        parent_row = execute_one(
            "SELECT revision_id FROM config_revisions WHERE scope = %s AND is_active = TRUE ORDER BY created_at DESC LIMIT 1",
            (scope,),
        )
        execute(
            "INSERT INTO config_revisions (revision_id, scope, values, schema_version, created_by, reason, parent_revision_id, is_active) "
            "VALUES (%s, %s, %s, '1', %s, %s, %s, FALSE)",
            (revision_id, scope, new_values, created_by, reason, parent_row["revision_id"] if parent_row else None),
        )
        AuditService.record(
            event_type="config.set",
            principal_id=created_by,
            resource_id=revision_id,
            action="set_config",
            result="success",
            details={"scope": scope, "key": key, "reason": reason},
        )
        return {"revision_id": revision_id, "scope": scope, "key": key, "value": value}

    @staticmethod
    def get_effective(scope: str) -> dict:
        result = {}
        for category in ["platform", "tenant"]:
            if scope.startswith(category) or scope == category:
                for k, v in CONFIG_SCHEMA.get(category, {}).items():
                    result[k] = v["default"]

        for s in ["platform", scope]:
            row = execute_one(
                "SELECT values FROM config_revisions WHERE scope = %s AND is_active = TRUE ORDER BY created_at DESC LIMIT 1",
                (s,),
            )
            if row:
                for k, v in row["values"].items():
                    if k not in IMMUTABLE_KEYS:
                        result[k] = v
        return result

    @staticmethod
    def activate(revision_id: str, activated_by: str) -> dict:
        row = execute_one(
            "SELECT scope, rollout_version FROM config_revisions WHERE revision_id = %s",
            (revision_id,),
        )
        if row is None:
            raise ValueError(f"Revision not found: {revision_id}")
        in_progress = execute_one(
            "SELECT revision_id FROM config_revisions WHERE scope = %s AND rollout_status = 'APPLYING'",
            (row["scope"],),
        )
        if in_progress:
            raise ValueError("ROLLOUT_IN_PROGRESS")
        execute(
            "UPDATE config_revisions SET is_active = FALSE, rollout_status = 'ROLLED_BACK' WHERE scope = %s AND is_active = TRUE",
            (row["scope"],),
        )
        new_version = (row["rollout_version"] or 0) + 1
        execute(
            "UPDATE config_revisions SET is_active = TRUE, activated_at = %s, rollout_status = 'ACTIVE', rollout_version = %s WHERE revision_id = %s",
            (datetime.now(timezone.utc), new_version, revision_id),
        )
        AuditService.record(
            event_type="config.activated",
            principal_id=activated_by,
            resource_id=revision_id,
            action="activate_config",
            result="success",
            details={"scope": row["scope"], "rollout_version": new_version},
        )
        return {"revision_id": revision_id, "activated": True, "rollout_version": new_version}

    @staticmethod
    def rollback(revision_id: str, rolled_back_by: str) -> dict:
        return ConfigurationService.activate(revision_id, rolled_back_by)

    @staticmethod
    def list_revisions(scope: str | None = None, page: int = 1, page_size: int = 50) -> dict:
        query = "SELECT revision_id, scope, created_by, reason, is_active, created_at, activated_at FROM config_revisions"
        params = None
        if scope:
            query += " WHERE scope = %s"
            params = (scope,)
        query += " ORDER BY created_at DESC"
        items = execute(query, params)
        total = len(items)
        offset = (page - 1) * page_size
        return {"items": items[offset:offset + page_size], "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def _get_defaults(scope: str, key: str | None = None) -> dict:
        category = scope.split(":")[0] if ":" in scope else scope
        schema = CONFIG_SCHEMA.get(category, {})
        if key:
            return {"key": key, "value": schema.get(key, {}).get("default")}
        return {"scope": scope, "values": {k: v["default"] for k, v in schema.items()}}
