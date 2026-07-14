from __future__ import annotations
from datetime import datetime, timezone
import ulid
from ..db import execute, execute_one
from ..security.crypto import encrypt, decrypt
from .audit_service import AuditService


def _ulid(prefix: str) -> str:
    return f"{prefix}_{str(ulid.new())}"


class SecretService:

    @staticmethod
    def create(scope: str, name: str, value: str, created_by: str) -> dict:
        secret_id = _ulid("sec")
        encrypted = encrypt(value, f"{scope}:{name}".encode())
        execute(
            "INSERT INTO v2_secrets (secret_id, scope, name, encrypted_value, version, created_by) "
            "VALUES (%s, %s, %s, %s, 1, %s)",
            (secret_id, scope, name, encrypted, created_by),
        )
        AuditService.record(
            event_type="secret.create",
            principal_id=created_by,
            resource_id=secret_id,
            action="create_secret",
            result="success",
            details={"scope": scope, "name": name},
        )
        return {"secret_id": secret_id, "scope": scope, "name": name, "ref": f"secret://{scope}/{name}"}

    @staticmethod
    def get_ref(scope: str, name: str) -> dict | None:
        return execute_one(
            "SELECT secret_id, scope, name, version, created_at, rotated_at FROM v2_secrets "
            "WHERE scope = %s AND name = %s ORDER BY version DESC LIMIT 1",
            (scope, name),
        )

    @staticmethod
    def resolve(ref: str, requester_id: str) -> str:
        parts = ref.replace("secret://", "").split("/")
        if len(parts) < 2:
            raise ValueError(f"Invalid secret ref: {ref}")
        scope, name = parts[0], parts[1]
        row = execute_one(
            "SELECT encrypted_value FROM v2_secrets WHERE scope = %s AND name = %s ORDER BY version DESC LIMIT 1",
            (scope, name),
        )
        if row is None:
            raise ValueError(f"Secret not found: {ref}")
        plaintext = decrypt(row["encrypted_value"], f"{scope}:{name}".encode())
        AuditService.record(
            event_type="secret.use",
            principal_id=requester_id,
            resource_id=ref,
            action="resolve_secret",
            result="success",
            details={"scope": scope, "name": name},
        )
        return plaintext

    @staticmethod
    def rotate(scope: str, name: str, new_value: str, rotated_by: str) -> dict:
        old = SecretService.get_ref(scope, name)
        if old is None:
            raise ValueError(f"Secret not found: {scope}/{name}")
        secret_id = _ulid("sec")
        encrypted = encrypt(new_value, f"{scope}:{name}".encode())
        execute(
            "INSERT INTO v2_secrets (secret_id, scope, name, encrypted_value, version, created_by, rotated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (secret_id, scope, name, encrypted, old["version"] + 1, rotated_by, datetime.now(timezone.utc)),
        )
        AuditService.record(
            event_type="secret.rotate",
            principal_id=rotated_by,
            resource_id=secret_id,
            action="rotate_secret",
            result="success",
            details={"scope": scope, "name": name, "new_version": old["version"] + 1},
        )
        return {"secret_id": secret_id, "scope": scope, "name": name, "version": old["version"] + 1}

    @staticmethod
    def list(scope: str | None = None) -> list[dict]:
        query = "SELECT secret_id, scope, name, version, created_at, rotated_at FROM v2_secrets"
        params = None
        if scope:
            query += " WHERE scope = %s"
            params = (scope,)
        query += " ORDER BY scope, name, version DESC"
        return execute(query, params)
