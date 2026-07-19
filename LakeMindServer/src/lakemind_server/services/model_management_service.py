from __future__ import annotations
import json
import ulid
from ..db import execute, execute_one
from ..security.context import SecurityContext
from .audit_service import AuditService
from .secret_service import SecretService


def _ulid(prefix: str) -> str:
    return f"{prefix}_{str(ulid.new())}"


class ModelManagementService:

    @staticmethod
    def create_model(
        name: str,
        model_type: str,
        capabilities: list[str],
        provider_family: str,
        context_length: int | None = None,
        embedding_dim: int | None = None,
        modalities: list[str] | None = None,
        metadata: dict | None = None,
    ) -> dict:
        model_id = _ulid("mdl")
        execute(
            """
            INSERT INTO model_definitions
                (model_id, name, model_type, capabilities, provider_family,
                 context_length, embedding_dim, modalities, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (model_id, name, model_type, json.dumps(capabilities), provider_family,
             context_length, embedding_dim,
             json.dumps(modalities or ["text"]), json.dumps(metadata or {})),
        )
        return execute_one("SELECT * FROM model_definitions WHERE model_id = %s", (model_id,))

    @staticmethod
    def create_deployment(
        model_id: str,
        provider: str,
        endpoint: str,
        secret_ref: str,
        priority: int = 100,
        timeout_ms: int = 30000,
        max_concurrency: int = 10,
    ) -> dict:
        deployment_id = _ulid("dpl")
        execute(
            """
            INSERT INTO model_deployments
                (deployment_id, model_id, provider, endpoint, secret_ref,
                 priority, timeout_ms, max_concurrency, status, desired_state)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'disabled', 'DRAFT')
            """,
            (deployment_id, model_id, provider, endpoint, secret_ref,
             priority, timeout_ms, max_concurrency),
        )
        return execute_one("SELECT * FROM model_deployments WHERE deployment_id = %s", (deployment_id,))

    @staticmethod
    def create_profile(name: str, description: str | None = None) -> dict:
        profile_id = _ulid("prf")
        execute(
            "INSERT INTO model_profiles (profile_id, name, description) VALUES (%s, %s, %s)",
            (profile_id, name, description),
        )
        return execute_one("SELECT * FROM model_profiles WHERE profile_id = %s", (profile_id,))

    @staticmethod
    def create_route(
        profile_name: str,
        deployment_id: str,
        priority: int = 100,
        is_fallback: bool = False,
        tenant_id: str | None = None,
    ) -> dict:
        route_id = _ulid("rt")
        execute(
            """
            INSERT INTO model_routes
                (route_id, profile_name, deployment_id, priority, is_fallback, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (route_id, profile_name, deployment_id, priority, is_fallback, tenant_id),
        )
        return execute_one("SELECT * FROM model_routes WHERE route_id = %s", (route_id,))

    @staticmethod
    def create_embedding_space(
        model_id: str,
        model_revision: str,
        dimension: int,
        normalize: bool = True,
        distance_metric: str = "cosine",
    ) -> dict:
        space_id = _ulid("esp")
        execute(
            """
            INSERT INTO embedding_spaces
                (space_id, model_id, model_revision, dimension, normalize, distance_metric)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (space_id, model_id, model_revision, dimension, normalize, distance_metric),
        )
        return execute_one("SELECT * FROM embedding_spaces WHERE space_id = %s", (space_id,))

    @staticmethod
    def resolve_profile(profile_name: str, tenant_id: str | None = None) -> dict:
        routes = execute(
            """
            SELECT r.*, d.model_id, d.deployment_id, d.endpoint, d.secret_ref,
                   d.status, d.health_status, d.priority AS dep_priority,
                   m.model_type, m.embedding_dim, m.provider_family
            FROM model_routes r
            JOIN model_deployments d ON r.deployment_id = d.deployment_id
            JOIN model_definitions m ON d.model_id = m.model_id
            WHERE r.profile_name = %s
              AND (r.tenant_id IS NULL OR r.tenant_id = %s)
              AND d.status = 'enabled'
            ORDER BY r.priority ASC, d.priority ASC
            """,
            (profile_name, tenant_id),
        )

        if not routes:
            raise ValueError(f"MODEL_PROFILE_NOT_FOUND: {profile_name}")

        primary = routes[0]
        fallbacks = [r for r in routes[1:] if r["is_fallback"]]

        config_rev = execute_one(
            "SELECT revision_id FROM config_revisions WHERE is_active = TRUE ORDER BY activated_at DESC LIMIT 1"
        )

        embedding_space = None
        if primary["model_type"] == "embedding":
            esp = execute_one(
                "SELECT * FROM embedding_spaces WHERE model_id = %s ORDER BY created_at DESC LIMIT 1",
                (primary["model_id"],),
            )
            embedding_space = esp

        return {
            "profile_name": profile_name,
            "model_id": primary["model_id"],
            "deployment_id": primary["deployment_id"],
            "endpoint": primary["endpoint"],
            "model_type": primary["model_type"],
            "config_revision_id": config_rev["revision_id"] if config_rev else None,
            "embedding_space_id": embedding_space["space_id"] if embedding_space else None,
            "fallbacks": [{"deployment_id": f["deployment_id"], "model_id": f["model_id"]} for f in fallbacks],
        }

    @staticmethod
    def list_models(model_type: str | None = None) -> list[dict]:
        if model_type:
            return execute("SELECT * FROM model_definitions WHERE model_type = %s ORDER BY created_at", (model_type,))
        return execute("SELECT * FROM model_definitions ORDER BY created_at")

    @staticmethod
    def update_model(model_id: str, **fields) -> dict:
        existing = execute_one("SELECT * FROM model_definitions WHERE model_id = %s", (model_id,))
        if not existing:
            raise ValueError("MODEL_NOT_FOUND")
        allowed = {"name", "model_type", "capabilities", "provider_family",
                    "context_length", "embedding_dim", "modalities", "metadata"}
        sets = []
        params = []
        for k, v in fields.items():
            if k not in allowed or v is None:
                continue
            if k in ("capabilities", "modalities", "metadata"):
                v = json.dumps(v)
            sets.append(f"{k} = %s")
            params.append(v)
        if not sets:
            return existing
        params.append(model_id)
        execute(f"UPDATE model_definitions SET {', '.join(sets)} WHERE model_id = %s", tuple(params))
        return execute_one("SELECT * FROM model_definitions WHERE model_id = %s", (model_id,))

    @staticmethod
    def list_deployments(model_id: str | None = None) -> list[dict]:
        if model_id:
            return execute("SELECT * FROM model_deployments WHERE model_id = %s ORDER BY priority", (model_id,))
        return execute("SELECT * FROM model_deployments ORDER BY priority")

    @staticmethod
    def update_deployment(deployment_id: str, **fields) -> dict:
        existing = execute_one("SELECT * FROM model_deployments WHERE deployment_id = %s", (deployment_id,))
        if not existing:
            raise ValueError("DEPLOYMENT_NOT_FOUND")
        allowed = {"model_id", "provider", "endpoint", "secret_ref",
                    "priority", "timeout_ms", "max_concurrency", "status"}
        sets = []
        params = []
        for k, v in fields.items():
            if k not in allowed or v is None:
                continue
            sets.append(f"{k} = %s")
            params.append(v)
        if not sets:
            return existing
        params.append(deployment_id)
        execute(f"UPDATE model_deployments SET {', '.join(sets)} WHERE deployment_id = %s", tuple(params))
        return execute_one("SELECT * FROM model_deployments WHERE deployment_id = %s", (deployment_id,))

    @staticmethod
    def list_profiles() -> list[dict]:
        return execute("SELECT * FROM model_profiles ORDER BY created_at")

    @staticmethod
    def list_routes(profile_name: str | None = None) -> list[dict]:
        if profile_name:
            return execute("SELECT * FROM model_routes WHERE profile_name = %s ORDER BY priority", (profile_name,))
        return execute("SELECT * FROM model_routes ORDER BY priority")

    @staticmethod
    def enable_deployment(ctx: SecurityContext, deployment_id: str) -> dict:
        execute(
            "UPDATE model_deployments SET status = 'enabled', desired_state = 'ACTIVE' WHERE deployment_id = %s",
            (deployment_id,),
        )
        event_id = _ulid("evt")
        execute(
            "INSERT INTO outbox (event_id, event_type, aggregate_id, aggregate_type, payload, status) "
            "VALUES (%s, 'DEPLOYMENT_ENABLE', %s, 'model_deployment', %s::jsonb, 'PENDING')",
            (event_id, deployment_id, json.dumps({"deployment_id": deployment_id, "desired_state": "ACTIVE"})),
        )
        AuditService.record(
            event_type="model.deployment_enable_requested",
            principal_id=ctx.principal_id,
            tenant_id=ctx.tenant_id,
            resource_id=deployment_id,
            action="model.configure",
            result="success",
        )
        return execute_one("SELECT * FROM model_deployments WHERE deployment_id = %s", (deployment_id,))

    @staticmethod
    def disable_deployment(ctx: SecurityContext, deployment_id: str) -> dict:
        execute(
            "UPDATE model_deployments SET status = 'disabled', desired_state = 'DISABLED' WHERE deployment_id = %s",
            (deployment_id,),
        )
        event_id = _ulid("evt")
        execute(
            "INSERT INTO outbox (event_id, event_type, aggregate_id, aggregate_type, payload, status) "
            "VALUES (%s, 'DEPLOYMENT_DISABLE', %s, 'model_deployment', %s::jsonb, 'PENDING')",
            (event_id, deployment_id, json.dumps({"deployment_id": deployment_id, "desired_state": "DISABLED"})),
        )
        AuditService.record(
            event_type="model.deployment_disable_requested",
            principal_id=ctx.principal_id,
            tenant_id=ctx.tenant_id,
            resource_id=deployment_id,
            action="model.configure",
            result="success",
        )
        return execute_one("SELECT * FROM model_deployments WHERE deployment_id = %s", (deployment_id,))

    @staticmethod
    def test_deployment(deployment_id: str) -> dict:
        import time
        import httpx

        dep = execute_one("SELECT * FROM model_deployments WHERE deployment_id = %s", (deployment_id,))
        if not dep:
            raise ValueError("DEPLOYMENT_NOT_FOUND")
        model = execute_one("SELECT * FROM model_definitions WHERE model_id = %s", (dep["model_id"],))
        if not model:
            raise ValueError("MODEL_NOT_FOUND")

        endpoint = dep["endpoint"]
        model_type = model["model_type"]
        model_name = model["name"]

        api_key = "lakemind-modelserving-key"
        secret_ref = dep.get("secret_ref", "")
        if secret_ref.startswith("secret://"):
            try:
                api_key = SecretService.resolve(secret_ref, "system")
            except Exception:
                pass
        elif secret_ref and secret_ref != "modelserving-key":
            api_key = secret_ref

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        timeout = max(dep.get("timeout_ms", 30000) / 1000, 10)

        result = {
            "deployment_id": deployment_id,
            "endpoint": endpoint,
            "model_type": model_type,
            "model_name": model_name,
            "success": False,
            "latency_ms": None,
            "status_code": None,
            "error": None,
            "response_preview": None,
        }

        try:
            t0 = time.time()
            if model_type == "chat":
                payload = {"model": model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
                r = httpx.post(endpoint, json=payload, headers=headers, timeout=timeout)
            elif model_type == "embedding":
                payload = {"model": model_name, "input": ["test"]}
                r = httpx.post(endpoint, json=payload, headers=headers, timeout=timeout)
            elif model_type == "asr":
                base_url = endpoint.split("/api/v1/")[0] if "/api/v1/" in endpoint else endpoint.rsplit("/", 3)[0]
                r = httpx.get(f"{base_url}/health", headers=headers, timeout=timeout)
            else:
                r = httpx.get(endpoint, headers=headers, timeout=timeout)

            result["latency_ms"] = int((time.time() - t0) * 1000)
            result["status_code"] = r.status_code
            result["success"] = r.status_code < 400
            result["response_preview"] = r.text[:500]
            if not result["success"]:
                result["error"] = f"HTTP {r.status_code}: {r.text[:200]}"
        except httpx.ConnectError as e:
            result["error"] = f"Connection failed: {e}"
        except httpx.TimeoutException:
            result["error"] = f"Timeout after {timeout}s"
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"

        new_status = "healthy" if result["success"] else "unhealthy"
        execute(
            "UPDATE model_deployments SET health_status = %s, test_state = %s WHERE deployment_id = %s",
            (new_status, "PASSED" if result["success"] else "FAILED", deployment_id),
        )
        result["health_status"] = new_status
        return result

    @staticmethod
    def delete_route(route_id: str) -> dict:
        existing = execute_one("SELECT * FROM model_routes WHERE route_id = %s", (route_id,))
        if not existing:
            raise ValueError("ROUTE_NOT_FOUND")
        execute("DELETE FROM model_routes WHERE route_id = %s", (route_id,))
        return existing

    @staticmethod
    def update_profile(profile_id: str, name: str | None = None, description: str | None = None) -> dict:
        existing = execute_one("SELECT * FROM model_profiles WHERE profile_id = %s", (profile_id,))
        if not existing:
            raise ValueError("PROFILE_NOT_FOUND")
        sets, params = [], []
        if name is not None:
            sets.append("name = %s"); params.append(name)
        if description is not None:
            sets.append("description = %s"); params.append(description)
        if not sets:
            return existing
        params.append(profile_id)
        execute(f"UPDATE model_profiles SET {', '.join(sets)} WHERE profile_id = %s", tuple(params))
        return execute_one("SELECT * FROM model_profiles WHERE profile_id = %s", (profile_id,))

    @staticmethod
    def update_health(deployment_id: str, health_status: str, latency_ms: int | None = None) -> dict:
        execute(
            "UPDATE model_deployments SET health_status = %s WHERE deployment_id = %s",
            (health_status, deployment_id),
        )
        return execute_one("SELECT * FROM model_deployments WHERE deployment_id = %s", (deployment_id,))

    @staticmethod
    def import_from_yaml(yaml_path: str) -> dict:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        imported = {"models": 0, "deployments": 0, "profiles": 0, "routes": 0}

        for model_def in config.get("models", []):
            existing = execute_one(
                "SELECT model_id FROM model_definitions WHERE name = %s",
                (model_def["name"],),
            )
            if existing:
                continue
            ModelManagementService.create_model(
                name=model_def["name"],
                model_type=model_def["type"],
                capabilities=model_def.get("capabilities", []),
                provider_family=model_def["provider_family"],
                context_length=model_def.get("context_length"),
                embedding_dim=model_def.get("embedding_dim"),
                modalities=model_def.get("modalities"),
                metadata=model_def.get("metadata"),
            )
            imported["models"] += 1

            for dep in model_def.get("deployments", []):
                model = execute_one(
                    "SELECT model_id FROM model_definitions WHERE name = %s",
                    (model_def["name"],),
                )
                ModelManagementService.create_deployment(
                    model_id=model["model_id"],
                    provider=dep["provider"],
                    endpoint=dep["endpoint"],
                    secret_ref=dep["secret_ref"],
                    priority=dep.get("priority", 100),
                )
                imported["deployments"] += 1

        for profile in config.get("profiles", []):
            existing = execute_one(
                "SELECT profile_id FROM model_profiles WHERE name = %s",
                (profile["name"],),
            )
            if existing:
                continue
            ModelManagementService.create_profile(profile["name"], profile.get("description"))
            imported["profiles"] += 1

            for route in profile.get("routes", []):
                dep = execute_one(
                    "SELECT deployment_id FROM model_deployments WHERE deployment_id = %s",
                    (route["deployment_id"],),
                )
                if dep:
                    ModelManagementService.create_route(
                        profile_name=profile["name"],
                        deployment_id=route["deployment_id"],
                        priority=route.get("priority", 100),
                        is_fallback=route.get("is_fallback", False),
                    )
                    imported["routes"] += 1

        return imported
