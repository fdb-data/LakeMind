from __future__ import annotations


def resolve_s3_key(tenant_id: str, asset_id: str, binding_id: str, filename: str) -> str:
    return f"{tenant_id}/{asset_id}/{binding_id}/{filename}"


def resolve_s3_bucket(tenant_id: str) -> str:
    return f"lakemind-{tenant_id}"


def resolve_lance_uri(tenant_id: str, asset_id: str) -> str:
    return f"{tenant_id}/{asset_id}/vector"


def resolve_iceberg_namespace(tenant_id: str, asset_type: str) -> str:
    return f"{tenant_id}.{asset_type}"


def resolve_valkey_key(tenant_id: str, key: str) -> str:
    return f"{tenant_id}:{key}"


def resolve_valkey_db(tenant_id: str) -> int:
    return hash(tenant_id) % 16
