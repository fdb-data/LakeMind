#!/usr/bin/env python3
"""LakeMind v0.2.0 Bootstrap — initialize admin, master key, default config, model import."""
from __future__ import annotations
import os
import sys
import base64
import json
import secrets as pysecrets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lakemind_server.db import init_pool, execute, execute_one
from lakemind_server.security.token_parser import issue_token, create_principal, assign_role
from lakemind_server.services.model_management_service import ModelManagementService


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

    bootstrap_models()


def bootstrap_models():
    yaml_path = os.environ.get("LAKE_CONFIG", "/etc/lakemind/models.yaml")
    if not os.path.exists(yaml_path):
        print(f"Models config not found at {yaml_path}, skipping model bootstrap.")
        return

    existing = execute_one("SELECT COUNT(*) AS cnt FROM model_definitions")
    if existing and existing["cnt"] > 0:
        print(f"Model definitions already exist ({existing['cnt']}), skipping model bootstrap.")
        return

    import yaml
    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    model_serving_url = os.environ.get("MODEL_SERVING_URL", "http://lakemind-model-serving:10824")
    imported = {"models": 0, "deployments": 0, "profiles": 0, "routes": 0, "embedding_spaces": 0}

    for provider in config.get("llm_providers", []):
        for m in provider.get("models", []):
            tags = m.get("tags", ["chat"])
            model = ModelManagementService.create_model(
                name=m["id"],
                model_type="chat" if "chat" in tags else "completion",
                capabilities=tags,
                provider_family=provider["type"],
                context_length=m.get("context"),
                metadata={"litellm_model": m.get("litellm_model", m["id"]), "provider_name": provider["name"]},
            )
            imported["models"] += 1

            dep = ModelManagementService.create_deployment(
                model_id=model["model_id"],
                provider=provider["type"],
                endpoint=f"{model_serving_url}/v1/chat/completions",
                secret_ref=f"secret://default/{provider['name']}-api-key",
                priority=provider.get("priority", 100),
            )
            imported["deployments"] += 1

    emb = config.get("embedding", {}).get("built_in", {})
    if emb.get("enabled"):
        model = ModelManagementService.create_model(
            name=emb["model"],
            model_type="embedding",
            capabilities=["embed"],
            provider_family=emb.get("provider", "fastembed"),
            embedding_dim=emb.get("dim", 768),
            metadata={"cache_dir": emb.get("cache_dir", "/data/fastembed_cache")},
        )
        imported["models"] += 1

        dep = ModelManagementService.create_deployment(
            model_id=model["model_id"],
            provider=emb.get("provider", "fastembed"),
            endpoint=f"{model_serving_url}/v1/embeddings",
            secret_ref="secret://default/embedding-internal",
            priority=1,
        )
        imported["deployments"] += 1

        esp = ModelManagementService.create_embedding_space(
            model_id=model["model_id"],
            model_revision="v1",
            dimension=emb.get("dim", 768),
        )
        imported["embedding_spaces"] += 1

    asr_cfg = config.get("asr", {}).get("built_in", {})
    if asr_cfg.get("enabled"):
        model = ModelManagementService.create_model(
            name=asr_cfg["model"],
            model_type="asr",
            capabilities=["transcribe"],
            provider_family=asr_cfg.get("provider", "funasr"),
            metadata={"language": asr_cfg.get("language", "auto"), "cache_dir": asr_cfg.get("cache_dir")},
        )
        imported["models"] += 1

        dep = ModelManagementService.create_deployment(
            model_id=model["model_id"],
            provider=asr_cfg.get("provider", "funasr"),
            endpoint=f"{model_serving_url}/api/v1/asr/transcribe",
            secret_ref="secret://default/asr-internal",
            priority=1,
        )
        imported["deployments"] += 1

    gw = config.get("gateway", {})
    profile = ModelManagementService.create_profile(
        name="default",
        description="Default model routing profile",
    )
    imported["profiles"] += 1

    all_deps = ModelManagementService.list_deployments()
    for dep in all_deps:
        is_fallback = False
        model_def = execute_one("SELECT * FROM model_definitions WHERE model_id = %s", (dep["model_id"],))
        if model_def and model_def["model_type"] == "chat":
            is_fallback = model_def["name"] in gw.get("fallback", {}).get("chat", [])
        ModelManagementService.create_route(
            profile_name="default",
            deployment_id=dep["deployment_id"],
            priority=dep["priority"],
            is_fallback=is_fallback,
        )
        imported["routes"] += 1

    print(f"\n=== Model Bootstrap Complete ===")
    print(f"  Models: {imported['models']}")
    print(f"  Deployments: {imported['deployments']}")
    print(f"  Profiles: {imported['profiles']}")
    print(f"  Routes: {imported['routes']}")
    print(f"  Embedding Spaces: {imported['embedding_spaces']}")


if __name__ == "__main__":
    bootstrap()
