#!/usr/bin/env python3
"""LakeMind v0.2.0 Bootstrap — initialize admin, master key, default config."""
from __future__ import annotations
import os
import sys
import base64
import json
import secrets as pysecrets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lakemind_server.db import init_pool, execute, execute_one
from lakemind_server.security.token_parser import issue_token, create_principal, assign_role


def bootstrap():
    init_pool()

    admin_row = execute_one(
        "SELECT principal_id FROM principals WHERE principal_type = 'user' AND name = 'admin'"
    )
    if admin_row:
        print("Admin already exists. Skipping admin bootstrap.")
    else:
        print("Creating platform admin...")
        principal = create_principal(
            principal_type="user",
            name="admin",
            tenant_id="ten_default",
            metadata={"description": "Platform administrator"},
        )
        assign_role(principal["principal_id"], "platform_admin", "ten_default")

        token = issue_token(
            principal_id=principal["principal_id"],
            tenant_id="ten_default",
            scopes=[
                "asset:create", "asset:read", "asset:update", "asset:delete",
                "knowledge:ingest", "knowledge:search", "knowledge:reindex",
                "skill:register", "skill:publish", "skill:execute", "skill:revoke",
                "memory:add", "memory:read", "memory:update", "memory:delete", "memory:clear",
                "job:submit", "job:read", "job:cancel", "job:retry",
                "model:read", "model:configure", "model:use",
                "secret:use", "secret:rotate",
                "operation:request", "operation:approve",
                "config:read", "config:write", "config:activate",
                "audit:read",
            ],
        )

        print(f"\n=== Admin Bootstrap Complete ===")
        print(f"Admin Principal ID: {principal['principal_id']}")
        print(f"Admin Token (save this - shown only once):")
        print(f"  {token['token']}")


if __name__ == "__main__":
    bootstrap()
