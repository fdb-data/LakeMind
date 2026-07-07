"""Admin face platform management tools — REST API client version."""
from __future__ import annotations
from typing import Any

from ..server_client import ServerClient
from ._helpers import audited, require_scope

SCOPE = "admin"


def register(mcp, server: ServerClient, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def create_user(username: str, tenant_id: str, role: str = "user") -> dict[str, Any]:
        """Create a user."""
        require_scope(SCOPE)
        return await server.user_create(username, tenant_id, role)

    @mcp.tool()
    @audited(redact_keys)
    async def update_user(user_id: str, username: str | None = None, role: str | None = None, status: str | None = None) -> dict[str, Any]:
        """Update user."""
        require_scope(SCOPE)
        return await server.user_update(user_id, username, role, status)

    @mcp.tool()
    @audited(redact_keys)
    async def delete_user(user_id: str) -> dict[str, Any]:
        """Soft delete user."""
        require_scope(SCOPE)
        return await server.user_delete(user_id)

    @mcp.tool()
    @audited(redact_keys)
    async def list_users(tenant_id: str | None = None) -> dict[str, Any]:
        """List users."""
        require_scope(SCOPE)
        return await server.user_list(tenant_id)

    @mcp.tool()
    @audited(redact_keys)
    async def create_tenant(tenant_id: str, name: str) -> dict[str, Any]:
        """Create tenant."""
        require_scope(SCOPE)
        return await server.tenant_create(tenant_id, name)

    @mcp.tool()
    @audited(redact_keys)
    async def update_tenant(tenant_id: str, name: str | None = None, status: str | None = None) -> dict[str, Any]:
        """Update tenant."""
        require_scope(SCOPE)
        return await server.tenant_update(tenant_id, name, status)

    @mcp.tool()
    @audited(redact_keys)
    async def delete_tenant(tenant_id: str) -> dict[str, Any]:
        """Soft delete tenant."""
        require_scope(SCOPE)
        return await server.tenant_delete(tenant_id)

    @mcp.tool()
    @audited(redact_keys)
    async def list_tenants() -> dict[str, Any]:
        """List tenants."""
        require_scope(SCOPE)
        return await server.tenant_list()

    @mcp.tool()
    @audited(redact_keys)
    async def issue_token(agent_id: str, tenant_id: str, scopes: list[str]) -> dict[str, Any]:
        """Issue a new token."""
        require_scope(SCOPE)
        return await server.token_issue(agent_id, tenant_id, scopes)

    @mcp.tool()
    @audited(redact_keys)
    async def revoke_token(token: str) -> dict[str, Any]:
        """Revoke token."""
        require_scope(SCOPE)
        return await server.token_revoke(token)

    @mcp.tool()
    @audited(redact_keys)
    async def list_tokens(tenant_id: str | None = None, agent_id: str | None = None) -> dict[str, Any]:
        """List tokens."""
        require_scope(SCOPE)
        return await server.token_list(tenant_id, agent_id)

    @mcp.tool()
    @audited(redact_keys)
    async def register_asset_type(yaml_def: str) -> dict[str, Any]:
        """Register a new asset type from YAML definition."""
        require_scope(SCOPE)
        import yaml as yamllib
        defn = yamllib.safe_load(yaml_def)
        atype = defn.get("type", "unknown")
        return await server.asset_type_register(atype, yaml_def)

    @mcp.tool()
    @audited(redact_keys)
    async def unregister_asset_type(type: str) -> dict[str, Any]:
        """Remove asset type."""
        require_scope(SCOPE)
        return await server.asset_type_unregister(type)

    @mcp.tool()
    @audited(redact_keys)
    async def list_asset_types() -> dict[str, Any]:
        """List all registered asset types."""
        require_scope(SCOPE)
        return await server.asset_type_list()

    @mcp.tool()
    @audited(redact_keys)
    async def get_platform_health() -> dict[str, Any]:
        """Check platform health."""
        require_scope(SCOPE)
        return await server.health()

    @mcp.tool()
    @audited(redact_keys)
    async def get_node_status() -> dict[str, Any]:
        """Get service node status."""
        require_scope(SCOPE)
        return await server.nodes()

    @mcp.tool()
    @audited(redact_keys)
    async def get_metrics() -> dict[str, Any]:
        """Get platform metrics (engine health summary)."""
        require_scope(SCOPE)
        return await server.metrics()

    # ── Tenant Secrets ──

    @mcp.tool()
    @audited(redact_keys + ["value"])
    async def create_secret(key_name: str, value: str, description: str = "") -> dict[str, Any]:
        """Create or update a tenant secret (encrypted at rest)."""
        require_scope(SCOPE)
        return await server.secret_create(key_name, value, description)

    @mcp.tool()
    @audited(redact_keys + ["value"])
    async def update_secret(key_name: str, value: str, description: str = "") -> dict[str, Any]:
        """Update an existing tenant secret."""
        require_scope(SCOPE)
        return await server.secret_update(key_name, value, description)

    @mcp.tool()
    @audited(redact_keys)
    async def delete_secret(key_name: str) -> dict[str, Any]:
        """Delete a tenant secret."""
        require_scope(SCOPE)
        return await server.secret_delete(key_name)

    @mcp.tool()
    @audited(redact_keys)
    async def list_secrets() -> dict[str, Any]:
        """List tenant secret names and metadata (values not returned)."""
        require_scope(SCOPE)
        return await server.secret_list()
