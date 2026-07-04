"""Admin face platform management tools."""
from __future__ import annotations
import uuid
from typing import Any
import psycopg2
import json
from ..config import Config
from ..context import get_identity
from ._helpers import audited, require_scope

SCOPE = "admin"

def _conn(config: Config):
    return psycopg2.connect(
        host=config.postgres.host, port=config.postgres.port,
        dbname=config.postgres.db, user=config.postgres.user,
        password=config.postgres.password,
    )

def register(mcp, config: Config, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def create_user(username: str, tenant_id: str, role: str = "user") -> dict[str, Any]:
        """Create a user."""
        require_scope(SCOPE)
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        with _conn(config) as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO users (user_id, username, tenant_id, role) VALUES (%s,%s,%s,%s)", (user_id, username, tenant_id, role))
        return {"user_id": user_id, "username": username, "tenant_id": tenant_id, "role": role}

    @mcp.tool()
    @audited(redact_keys)
    async def update_user(user_id: str, username: str | None = None, role: str | None = None, status: str | None = None) -> dict[str, Any]:
        """Update user."""
        require_scope(SCOPE)
        sets = []
        vals = []
        if username: sets.append("username=%s"); vals.append(username)
        if role: sets.append("role=%s"); vals.append(role)
        if status: sets.append("status=%s"); vals.append(status)
        if not sets: return {"user_id": user_id, "updated": False}
        vals.append(user_id)
        with _conn(config) as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE users SET {','.join(sets)} WHERE user_id=%s", vals)
        return {"user_id": user_id, "updated": True}

    @mcp.tool()
    @audited(redact_keys)
    async def delete_user(user_id: str) -> dict[str, Any]:
        """Soft delete user."""
        require_scope(SCOPE)
        with _conn(config) as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET status='deleted' WHERE user_id=%s", (user_id,))
        return {"user_id": user_id, "deleted": True}

    @mcp.tool()
    @audited(redact_keys)
    async def list_users(tenant_id: str | None = None) -> dict[str, Any]:
        """List users."""
        require_scope(SCOPE)
        with _conn(config) as conn, conn.cursor() as cur:
            if tenant_id:
                cur.execute("SELECT user_id, username, tenant_id, role, status FROM users WHERE tenant_id=%s", (tenant_id,))
            else:
                cur.execute("SELECT user_id, username, tenant_id, role, status FROM users")
            users = [{"user_id": r[0], "username": r[1], "tenant_id": r[2], "role": r[3], "status": r[4]} for r in cur.fetchall()]
        return {"users": users, "count": len(users)}

    @mcp.tool()
    @audited(redact_keys)
    async def create_tenant(tenant_id: str, name: str) -> dict[str, Any]:
        """Create tenant."""
        require_scope(SCOPE)
        with _conn(config) as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id, name) VALUES (%s,%s) ON CONFLICT DO NOTHING", (tenant_id, name))
        return {"tenant_id": tenant_id, "name": name}

    @mcp.tool()
    @audited(redact_keys)
    async def update_tenant(tenant_id: str, name: str | None = None, status: str | None = None) -> dict[str, Any]:
        """Update tenant."""
        require_scope(SCOPE)
        sets = []
        vals = []
        if name: sets.append("name=%s"); vals.append(name)
        if status: sets.append("status=%s"); vals.append(status)
        if not sets: return {"tenant_id": tenant_id, "updated": False}
        vals.append(tenant_id)
        with _conn(config) as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE tenants SET {','.join(sets)} WHERE tenant_id=%s", vals)
        return {"tenant_id": tenant_id, "updated": True}

    @mcp.tool()
    @audited(redact_keys)
    async def delete_tenant(tenant_id: str) -> dict[str, Any]:
        """Soft delete tenant."""
        require_scope(SCOPE)
        with _conn(config) as conn, conn.cursor() as cur:
            cur.execute("UPDATE tenants SET status='deleted' WHERE tenant_id=%s", (tenant_id,))
            cur.execute("UPDATE users SET status='disabled' WHERE tenant_id=%s", (tenant_id,))
        return {"tenant_id": tenant_id, "deleted": True}

    @mcp.tool()
    @audited(redact_keys)
    async def list_tenants() -> dict[str, Any]:
        """List tenants."""
        require_scope(SCOPE)
        with _conn(config) as conn, conn.cursor() as cur:
            cur.execute("SELECT tenant_id, name, status FROM tenants")
            tenants = [{"tenant_id": r[0], "name": r[1], "status": r[2]} for r in cur.fetchall()]
        return {"tenants": tenants, "count": len(tenants)}

    @mcp.tool()
    @audited(redact_keys)
    async def issue_token(agent_id: str, tenant_id: str, scopes: list[str]) -> dict[str, Any]:
        """Issue a new token."""
        require_scope(SCOPE)
        token = f"tk_{uuid.uuid4().hex[:16]}"
        with _conn(config) as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO tokens (token, agent_id, tenant_id, scopes) VALUES (%s,%s,%s,%s)", (token, agent_id, tenant_id, scopes))
        return {"token": token, "agent_id": agent_id, "tenant_id": tenant_id, "scopes": scopes}

    @mcp.tool()
    @audited(redact_keys)
    async def revoke_token(token: str) -> dict[str, Any]:
        """Revoke token."""
        require_scope(SCOPE)
        with _conn(config) as conn, conn.cursor() as cur:
            cur.execute("UPDATE tokens SET status='revoked', revoked_at=now() WHERE token=%s", (token,))
        return {"token": token, "revoked": True}

    @mcp.tool()
    @audited(redact_keys)
    async def list_tokens(tenant_id: str | None = None, agent_id: str | None = None) -> dict[str, Any]:
        """List tokens."""
        require_scope(SCOPE)
        with _conn(config) as conn, conn.cursor() as cur:
            query = "SELECT token, agent_id, tenant_id, scopes, status FROM tokens"
            conditions = []
            vals = []
            if tenant_id: conditions.append("tenant_id=%s"); vals.append(tenant_id)
            if agent_id: conditions.append("agent_id=%s"); vals.append(agent_id)
            if conditions: query += " WHERE " + " AND ".join(conditions)
            cur.execute(query, vals)
            tokens = [{"token": r[0], "agent_id": r[1], "tenant_id": r[2], "scopes": r[3], "status": r[4]} for r in cur.fetchall()]
        return {"tokens": tokens, "count": len(tokens)}

    @mcp.tool()
    @audited(redact_keys)
    async def register_asset_type(yaml_def: str) -> dict[str, Any]:
        """Register a new asset type from YAML definition."""
        require_scope(SCOPE)
        import yaml as yamllib
        defn = yamllib.safe_load(yaml_def)
        atype = defn.get("type", "unknown")
        with _conn(config) as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO asset_types (type, definition_yaml) VALUES (%s,%s) ON CONFLICT (type) DO UPDATE SET definition_yaml=%s", (atype, yaml_def, yaml_def))
        return {"type": atype, "registered": True}

    @mcp.tool()
    @audited(redact_keys)
    async def unregister_asset_type(type: str) -> dict[str, Any]:
        """Remove asset type."""
        require_scope(SCOPE)
        with _conn(config) as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM asset_types WHERE type=%s", (type,))
        return {"type": type, "unregistered": True}

    @mcp.tool()
    @audited(redact_keys)
    async def get_platform_health() -> dict[str, Any]:
        """Check platform health (postgres + s3 + dragonfly + asset-mcp + data-mcp)."""
        require_scope(SCOPE)
        health = {}
        # Postgres
        try:
            with _conn(config) as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
            health["postgres"] = "ok"
        except Exception:
            health["postgres"] = "error"
        # S3
        try:
            import httpx
            r = httpx.get("http://lakemind-seaweedfs:8333", timeout=3)
            health["s3"] = "ok" if r.status_code < 500 else "error"
        except Exception:
            health["s3"] = "error"
        # Dragonfly
        try:
            import redis
            r = redis.Redis(host="lakemind-dragonfly", port=6379)
            r.ping()
            health["dragonfly"] = "ok"
        except Exception:
            health["dragonfly"] = "error"
        # MCP services
        for name, port in [("asset-mcp", 8401), ("data-mcp", 8402)]:
            try:
                import httpx
                r = httpx.get(f"http://lakemind-{name}:{port}/health", timeout=3)
                health[name] = "ok" if r.status_code == 200 else "error"
            except Exception:
                health[name] = "error"
        return health

    @mcp.tool()
    @audited(redact_keys)
    async def get_node_status() -> dict[str, Any]:
        """Get service node status."""
        require_scope(SCOPE)
        return {"nodes": ["postgres", "s3", "dragonfly", "asset-mcp", "data-mcp", "admin-mcp"], "status": "active"}
