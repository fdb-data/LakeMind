from __future__ import annotations


PROTECTED_PREFIXES = ("ten_", "ast_", "bnd_")


def is_protected(key: str) -> bool:
    parts = key.split("/")
    if len(parts) < 2:
        return False
    return parts[0].startswith("ten_") and len(parts) > 1 and parts[1].startswith("ast_")


def assert_writable(key: str, tenant_id: str, is_platform_admin: bool = False) -> None:
    if is_platform_admin:
        return
    if is_protected(key):
        parts = key.split("/")
        if parts[0] != tenant_id:
            raise PermissionError("PROTECTED_NAMESPACE_VIOLATION")
