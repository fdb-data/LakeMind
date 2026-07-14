from __future__ import annotations
from typing import Any


def resolve_job_secrets(skill_manifest: dict, caller_ctx, job_purpose: str) -> dict[str, str]:
    from ..services.secret_service import SecretService

    declarations = skill_manifest.get("secret_declarations", [])
    result: dict[str, str] = {}
    for ref in declarations:
        if not caller_ctx.has_scope("secret:use"):
            from ..services.audit_service import AuditService
            AuditService.record(
                event_type="secret.use",
                principal_id=caller_ctx.principal_id,
                resource_id=ref,
                action="resolve_secret",
                result="denied",
                details={"reason": "missing secret:use scope"},
            )
            continue
        if ref.startswith("secret://platform/"):
            continue
        try:
            value = SecretService.resolve(ref, caller_ctx.principal_id)
            result[ref] = value
        except Exception:
            pass
    return result


def get_control_plane_secrets() -> list[str]:
    return ["LAKEMIND_MASTER_KEY", "DATABASE_URL", "PG_PASSWORD"]
